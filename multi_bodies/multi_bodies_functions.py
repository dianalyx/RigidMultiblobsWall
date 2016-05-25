'''
In this module the user can define functions that modified the
code multi_blobs.py. For example, functions to define the
blobs-blobs interactions, the forces and torques on the rigid
bodies or the slip on the blobs.
'''
import numpy as np
import sys
import imp

from quaternion_integrator.quaternion import Quaternion
# Try to import the forces boost implementation
try:
  import forces_ext
except ImportError:
  pass
# If pycuda is installed import forces_pycuda
try: 
  imp.find_module('pycuda')
  found_pycuda = True
except ImportError:
  found_pycuda = False
if found_pycuda:
  import forces_pycuda  

def default_zero_r_vectors(r_vectors, *args, **kwargs):
  return np.zeros((r_vectors.size / 3, 3))

def default_zero_blobs(body, *args, **kwargs):
  ''' 
  Return a zero array of shape (body.Nblobs, 3)
  '''
  return np.zeros((body.Nblobs, 3))
  

def set_slip_by_ID(body):
  '''
  This functions assing a slip function to each
  body depending on his ID. The ID of a structure
  is the name of the clones file (without .clones)
  given in the input file.

  As an example we give a default function which sets the
  slip to zero and a function for active rods with an
  slip along its axis. The user can create new functions
  for other kind of active bodies.
  '''
  if body.ID == 'active_body':
    body.function_slip = active_body_slip
  else:
    body.function_slip = default_zero_blobs


def active_body_slip(body):
  '''
  This function set the slip on all the blobs of a body
  to a constant value along the x-axis in the body reference 
  configuration; i.e. if the body changes its orientation the
  slip will be along the rotated x-axis.
  
  This function can be used, for example, to model active rods
  that propel along their axes. 
  '''
  # Define slip speed
  speed = 1.0
  
  # Get main axis (rotated x-axis)
  rotation_matrix = body.orientation.rotation_matrix()
  x = np.zeros(3)
  x[0] = 1.0
  axis = np.dot(rotation_matrix, x)

  # Create slip on each blob
  slip = np.empty((body.Nblobs, 3))
  for i in range(body.Nblobs):
    slip[i] = speed * axis

  return slip


def bodies_external_force_torque(bodies, r_vectors, *args, **kwargs):
  '''
  This function returns the external force-torques acting on the bodies.
  It returns an array with shape (2*len(bodies), 3)
  
  In this is example we just set it to zero.
  '''
  return np.zeros((2*len(bodies), 3))
  

def blob_external_force(r_vectors, *args, **kwargs):
  '''
  This function compute the external force acting on a
  single blob. It returns an array with shape (3).
  
  In this example we add gravity and a repulsion with the wall;
  the interaction with the wall is derived from a Yukawa-like
  potential

  U = e * a * exp(-(h-a) / b) / (h - a)

  with 
  e = repulsion_strength_wall
  a = blob_radius
  h = distance to the wall
  b = debey_length_wall
  '''
  f = np.zeros(3)

  # Get parameters from arguments
  blob_mass = kwargs.get('blob_mass')
  blob_radius = kwargs.get('blob_radius')
  g = kwargs.get('g')
  repulsion_strength_wall = kwargs.get('repulsion_strength_wall')
  debey_length_wall = kwargs.get('debey_length_wall')
  
  # Add gravity
  f += -g * blob_mass * np.array([0., 0., 1.0])

  # Add wall interaction
  h = r_vectors[2]
  f += np.array([0., 0., (repulsion_strength_wall * \
                            ((h - blob_radius) / debey_length_wall + 1.0) * \
                            np.exp(-1.0 * (h - blob_radius) / debey_length_wall) / \
                            ((h - blob_radius)**2))])
  return f


def calc_one_blob_forces(r_vectors, *args, **kwargs):
  '''
  Compute one-blob forces. It returns an array with shape (Nblobs, 3).
  '''
  Nblobs = r_vectors.size / 3
  force_blobs = np.zeros((Nblobs, 3))
  r_vectors = np.reshape(r_vectors, (Nblobs, 3))
  
  # Loop over blobs
  for blob in range(Nblobs):
    force_blobs[blob] += blob_external_force(r_vectors[blob], *args, **kwargs)   

  return force_blobs


def set_blob_blob_forces(implementation):
  '''
  Set the function to compute the blob-blob forces
  to the rigth.

  The implementation in pycuda is much faster than the
  one in C++, which is much faster than the one python; 
  To use the pycuda implementation is necessary to have 
  installed pycuda and a GPU with CUDA capabilities. To
  use the C++ implementation the user has to compile 
  the file blob_blob_forces_ext.cc.   
  '''
  if implementation == 'None':
    return default_zero_r_vectors
  elif implementation == 'python':
    return calc_blob_blob_forces_python
  elif implementation == 'C++':
    return calc_blob_blob_forces_boost 
  elif implementation == 'pycuda':
    return forces_pycuda.calc_blob_blob_forces_pycuda


def blob_blob_force(r, *args, **kwargs):
  '''
  This function compute the force between two blobs
  with vector between blob centers r.

  In this example the force is derived from a Yukawa potential
  
  U = eps * exp(-r_norm / b) / r_norm
  
  with
  eps = potential strength
  r_norm = distance between blobs
  b = Debey length
  '''
  # Get parameters from arguments
  eps = kwargs.get('repulsion_strength')
  b = kwargs.get('debey_length')
  
  # Compute force
  r_norm = np.linalg.norm(r)
  return -((eps / b) + (eps / r_norm)) * np.exp(-r_norm / b) * r / r_norm**2
  

def calc_blob_blob_forces_python(r_vectors, *args, **kwargs):
  '''
  This function computes the blob-blob forces and returns
  an array with shape (Nblobs, 3).
  '''
  Nblobs = r_vectors.size / 3
  force_blobs = np.zeros((Nblobs, 3))

  # Double loop over blobs to compute forces
  for i in range(Nblobs-1):
    for j in range(i+1, Nblobs):
      # Compute vector from j to u
      r = r_vectors[j] - r_vectors[i]
      force = blob_blob_force(r, *args, **kwargs)
      force_blobs[i] += force
      force_blobs[j] -= force

  return force_blobs


def calc_blob_blob_forces_boost(r_vectors, *args, **kwargs):
  '''
  Call a boost function to compute the blob-blob forces.
  '''
  # Get parameters from arguments
  eps = kwargs.get('repulsion_strength')
  b = kwargs.get('debey_length')  

  number_of_blobs = r_vectors.size / 3
  r_vectors = np.reshape(r_vectors, (number_of_blobs, 3))
  forces = np.empty(r_vectors.size)

  forces_ext.calc_blob_blob_forces(r_vectors, forces, eps, b, number_of_blobs) 
  return np.reshape(forces, (number_of_blobs, 3))


def force_torque_calculator_sort_by_bodies(bodies, r_vectors, *args, **kwargs):
  '''
  Return the forces and torque in each body with
  format [f_1, t_1, f_2, t_2, ...] and shape (2*Nbodies, 3),
  where f_i and t_i are the force and torque in the body i.
  '''
  # Create auxiliar variables
  Nblobs = r_vectors.size / 3
  force_torque_bodies = np.zeros((2*len(bodies), 3))
  force_blobs = np.zeros((Nblobs, 3))
  blob_mass = 1.0
  blob_radius = bodies[0].blob_radius

  # Compute one-blob forces (same function for all blobs)
  force_blobs += calc_one_blob_forces(r_vectors, blob_radius = blob_radius, blob_mass = blob_mass, *args, **kwargs)

  # Compute blob-blob forces (same function for all blobs)
  force_blobs += calc_blob_blob_forces(r_vectors, blob_radius = blob_radius, *args, **kwargs)  

  # Compute body force-torque forces from blob forces
  offset = 0
  for k, b in enumerate(bodies):
    # Add force to the body
    force_torque_bodies[2*k:(2*k+1)] += sum(force_blobs[offset:(offset+b.Nblobs)])
    # Add torque to the body
    R = b.calc_rot_matrix()  
    force_torque_bodies[2*k+1:2*k+2] += np.dot(R.T, np.reshape(force_blobs[offset:(offset+b.Nblobs)], 3*b.Nblobs))
    offset += b.Nblobs

  # Add one-body external force-torque
  force_torque_bodies += bodies_external_force_torque(bodies, r_vectors, *args, **kwargs)
  
  return force_torque_bodies






























def force_torque_calculator_sort_by_bodies_(bodies, r_vectors, *args, **kwargs):
  '''
  Return the forces and torque in each body with
  format [f_1, t_1, f_2, t_2, ...] and shape (2*Nbodies, 3),
  where f_i and t_i are the force and torque in the body i.
  '''
  g = kwargs.get('g')
  repulsion_strength_wall = kwargs.get('repulsion_strength_wall')
  debey_length_wall = kwargs.get('debey_length_wall')

  force_torque_bodies = np.zeros((2*len(bodies), 3))
  offset = 0
  for k, b in enumerate(bodies):
    R = b.calc_rot_matrix()
    force_blobs = np.zeros((b.Nblobs, 3))
    # Compute forces on each blob
    for blob in range(b.Nblobs):
      h = r_vectors[offset+blob, 2]
      # Force on blob (wall repulsion + gravity)
      force_blobs[blob:(blob+1)] = np.array([0., 0., (repulsion_strength_wall * ((h - b.blob_radius)/debey_length_wall + 1.0) * \
                                                        np.exp(-1.0*(h - b.blob_radius)/debey_length_wall) / ((h - b.blob_radius)**2))])
      force_blobs[blob:(blob+1)] += - g * np.array([0.0, 0.0, b.blob_masses[blob]])

    # Add force to the body
    force_torque_bodies[2*k:(2*k+1)] += sum(force_blobs)
    # Add torque to the body
    force_torque_bodies[2*k+1:2*k+2] += np.dot(R.T, np.reshape(force_blobs, 3*b.Nblobs))
    offset += b.Nblobs
  return force_torque_bodies