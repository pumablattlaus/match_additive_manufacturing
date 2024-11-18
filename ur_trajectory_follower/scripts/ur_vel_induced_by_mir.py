#!/usr/bin/env python3

from match_lib.robot_mats.jacobians.jacobian_platform import getJacobianPlatformWithEEF
from helper.ur_helper import negateTwist
import numpy as np
import math
import rospy
from tf import TransformListener, transformations

from geometry_msgs.msg import PoseStamped, Pose, Twist, Transform


class UrMobileRobotCompensation():
        def __init__(self, base_mir="/mur620/base_link", base_ur="/mur620/UR10_r/base_ideal") -> None:
                
                # use parameters instead of hardcoded values
                self.base_mir_frame_id = rospy.get_param("~base_mir_frame_id", base_mir)
                self.base_ur_frame_id = rospy.get_param("~base_ur_frame_id", base_ur)

                self.ur_pose = Pose()
                self.mir_pose = Pose()
                self.mir_vel = Twist()
                self.listener = TransformListener()

                self.mir_ur_transform = Transform()
                self.get_mir_ur_transform()

                #Subscriber
                rospy.Subscriber("~ur_pose", PoseStamped, self.ur_pose_callback)
                rospy.Subscriber("~mir_cmd_vel", Twist, self.mir_cmd_vel_callback)

                #Publisher
                self.ur_cmd_vel_local_pub = rospy.Publisher("~ur_cmd_vel_local", Twist, queue_size=10)

        
        def ur_pose_callback(self, data = PoseStamped()):
            data = self.listener.transformPose(self.ur_base_link_frame_id, data)
            self.ur_pose = data.pose
        
        def mir_cmd_vel_callback(self, msg = Twist()):
            self.mir_vel = msg
            self.pub_induced_vel_compensation()
            
        def mir_pose_callback(self, msg = Pose()):
            self.mir_pose = msg


        def get_ee_vel_induced_by_mir(self, mir_vel_local: np.ndarray = np.zeros(3)):
            # get vector from mir_base to ee:
            rx,ry = self.ur_pose.position.x, self.ur_pose.position.y
            rx = rx + self.mir_ur_transform.translation.x
            ry = ry + self.mir_ur_transform.translation.y
            
            j_p = getJacobianPlatformWithEEF(rx, ry)
            return j_p@mir_vel_local

        def compute_mir_vel_global(self, mir_vel_local = Twist(),mir_angle = 0.0):
            mir_vel_global = Twist()
            mir_vel_global.linear.x = mir_vel_local.linear.x * math.cos(mir_angle) - mir_vel_local.linear.y * math.sin(mir_angle)
            mir_vel_global.linear.y = mir_vel_local.linear.x * math.sin(mir_angle) + mir_vel_local.linear.y * math.cos(mir_angle)
            mir_vel_global.angular.z = mir_vel_local.angular.z
            return mir_vel_global
        
        def get_mir_ur_transform(self):
            tf_listener = self.listener
            # wait for transform
            tf_listener.waitForTransform(self.base_mir_frame_id, self.base_ur_frame_id, rospy.Time(0), rospy.Duration(4.0))
            lin, ang = tf_listener.lookupTransform(self.base_mir_frame_id, self.base_ur_frame_id, rospy.Time(0))

            self.mir_ur_transform.translation.x = lin[0]
            self.mir_ur_transform.translation.y = lin[1]
            self.mir_ur_transform.translation.z = lin[2]
            q = transformations.quaternion_from_euler(ang[0], ang[1], ang[2])
            self.mir_ur_transform.rotation.x = q[0]
            self.mir_ur_transform.rotation.y = q[1]
            self.mir_ur_transform.rotation.z = q[2]
            self.mir_ur_transform.rotation.w = q[3]

        def pub_induced_vel_compensation(self):
            vel=-self.get_ee_vel_induced_by_mir((self.mir_vel.linear.x, self.mir_vel.linear.y, self.mir_vel.angular.z))
            ur_cmd_vel_local = Twist()
            ur_cmd_vel_local.linear.x, ur_cmd_vel_local.linear.y, ur_cmd_vel_local.linear.z, ur_cmd_vel_local.angular.x, ur_cmd_vel_local.angular.y, ur_cmd_vel_local.angular.z = vel

            self.ur_cmd_vel_local_pub.publish(ur_cmd_vel_local)

if __name__ == "__main__":
    rospy.init_node("ur_vel_induced_by_mir")
    ur_vel_induced_by_mir = UrMobileRobotCompensation()
    rospy.spin()
