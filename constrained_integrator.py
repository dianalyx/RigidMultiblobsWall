import sys

class ConstrainedIntegrator(object):
  """A class intended to test out temporal integration schemes
  for constrained diffusion. """

  def __init__(self, surface_function, mobility, scheme):
    """ Initialize  the integrator object, it needs a surface parameterization,
    a timestepping scheme, and a Mobility Matrix.

    args
      scheme:            string - must be one of "EULER" or "RFD".  EULER indicates
                           an unconstrained step that is projected back to the surface.
                           RFD gives a projected step using the Random Finite Difference to
                           generate the drift.
      surface_function:  function - takes the coordinates and returns the value of 
                           the constraint function.  
                           The constraint is such that surface_function(x) = 0.
      mobility:          matrix of floats - mobility matrix.  Stored as an array of arrays
                           with the first index representing the row. Must be a square matrix.
                                         
    """
    self.surface_function = surface_function
    self.mobility = mobility
    self.dim = len(mobility)
    for k in range(self.dim):
      if len(self.mobility[k]) != self.dim:
        print "Mobility Matrix must be square.  # rows is ", self.dim, 
        print " # Columns is ", len(self.mobility[k])
        sys.exit()

    self.current_time = 0.
    
    if scheme not in ["RFD", "EULER"]:
      print "Only RFD and Euler Schemes are implemented"
      raise NotImplementedError("Only RFD and Euler schemes are implemented")
    else:
      self.scheme = scheme
    
  def TimeStep(self, dt):
    """ Step from current time to next time with timestep of size dt.
     args
       dt: float - time step size.
     """
    if self.scheme == "RFD":
      self.RFDTimeStep(dt)
    elif self.scheme == "EULER":
      self.EulerTimeStep(dt)
    else:
      print "Should not get here in TimeStep."
      sys.exit()

  def ApplyMobility(self, force):
    """ Apply the mobility to a force in order to generate velocity.
    
    args
      force:    array of floats - input force to apply mobility to.
      
    output
      velocity: array of floats - velocity generated by force on particle.
                     velocity = mobility*force.
    """
    velocity = zeros(self.dim)
    for j in range(self.dim):
      for k in range(self.dim):
        velocity[j] += self.mobility[j][k]*force[k]
    return velocity

  def EulerTimeStep(self, dt):
    pass

  def RFDTimeStep(self, dt):
    pass

    
    
    
        
        
