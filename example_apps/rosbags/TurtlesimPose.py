from someipy.serialization import SomeIpPayload, Float32

# For defining the TurtleSimPose as a SOME/IP message, simply inherit from SomeIpPayload and use
# the provided datatypes such as Float32 for declaring the fields of the message
class TurtlesimPose(SomeIpPayload):
    x: Float32
    y: Float32
    theta: Float32
    linear_velocity: Float32
    angular_velocity: Float32

    def __init__(self):
        self.x = Float32()
        self.y = Float32()
        self.theta = Float32()
        self.linear_velocity = Float32()
        self.angular_velocity = Float32()
