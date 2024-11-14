#! /usr/bin/env python3
import rospy
import tf
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped, Quaternion
import numpy as np
from moveit_commander import MoveGroupCommander, roscpp_initialize, roscpp_shutdown
import sys
import tf.transformations as tr
from std_msgs.msg import Header
from geometry_msgs.msg import Point, Pose
from moveit_msgs.msg import DisplayTrajectory
import math


class MoveManipulatorToTarget:
    def __init__(self):
        rospy.init_node('move_manipulator_to_target', anonymous=True)


        # Initialize parameters
        self.path_topic = rospy.get_param('~path_topic', '/ur_path')
        self.manipulator_base_link = rospy.get_param('~manipulator_base_link', 'mur620a/UR10_r/base_link')
        
        # Initialize MoveIt
        roscpp_initialize(sys.argv)
        self.move_group = MoveGroupCommander("UR_arm_r", ns="/mur620a", robot_description="mur620a/robot_description")
        self.move_group.set_pose_reference_frame("UR10_r/base_link")
        rospy.loginfo("MoveIt MoveGroup for UR_arm_r initialized.")

        # Initialize the subscriber for the path
        self.path_sub = rospy.Subscriber(self.path_topic, Path, self.path_callback)
        
        # TF listener
        self.tf_listener = tf.TransformListener()

        # initialize the publisher for the target pose
        self.local_target_pose_pub = rospy.Publisher('/ur_local_target_pose', PoseStamped, queue_size=1)
        self.display_trajectory_publisher = rospy.Publisher('move_group/display_planned_path', DisplayTrajectory, queue_size=10)

    def path_callback(self, path_msg):
        if len(path_msg.poses) == 0:
            rospy.logwarn("Received an empty path!")
            return

        # Get the first TCP pose from the path
        target_tcp_pose = path_msg.poses[0]
        
        # Get the current pose of the manipulator base in the map frame
        try:
            now = rospy.Time.now()
            self.tf_listener.waitForTransform("map", self.manipulator_base_link, now, rospy.Duration(2.0))
            (trans, rot) = self.tf_listener.lookupTransform("map", self.manipulator_base_link, now)
        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException) as e:
            rospy.logerr(f"TF error: {e}")
            return
        
        # Convert to numpy arrays for easier manipulation
        manipulator_base_position = np.array(trans)
        target_tcp_position = np.array([target_tcp_pose.pose.position.x,
                                        target_tcp_pose.pose.position.y,
                                        target_tcp_pose.pose.position.z])
        
        # Compute the target position in the manipulator’s local frame
        relative_position = target_tcp_position - manipulator_base_position

        relative_pose = [0.0,0.0,0.0,0.0,0.0,0.0]
        relative_pose[0] = relative_position[0]
        relative_pose[1] = relative_position[1]
        relative_pose[2] = relative_position[2]
        relative_pose[3] = math.pi
        relative_pose[4] = 0.0
        relative_pose[5] = math.pi
        
        # Set the target pose for MoveIt
        #self.move_group.set_position_target(relative_position, end_effector_link="UR10_r/tool0" )
        self.move_group.set_pose_target(relative_pose, end_effector_link="UR10_r/tool0")
        local_target_pose = PoseStamped()
        local_target_pose.header.frame_id = "UR10_r/base_link"
        local_target_pose.header.stamp = rospy.Time.now()
        local_target_pose.pose.position.x = relative_position[0]
        local_target_pose.pose.position.y = relative_position[1]
        local_target_pose.pose.position.z = relative_position[2]
        self.local_target_pose_pub.publish(local_target_pose)

        
        # Plan and execute the motion
        plan_result = self.move_group.plan()

        if isinstance(plan_result, tuple):
            success = plan_result[0]  # Typically the success flag is the first item
            plan_trajectory = plan_result[1]  # The trajectory is usually the second item

            if success:
                # Publish the plan to the display path topic
                display_trajectory_publisher = rospy.Publisher('/display_planned_path', DisplayTrajectory, queue_size=10)
                display_trajectory = DisplayTrajectory()
                display_trajectory.trajectory_start = self.move_group.get_current_state()
                display_trajectory.trajectory.append(plan_trajectory)
                display_trajectory_publisher.publish(display_trajectory)

                # Execute the motion
                self.move_group.execute(plan_trajectory, wait=True)
                rospy.loginfo("Motion executed successfully.")
                rospy.signal_shutdown("Motion executed successfully.")
            else:
                rospy.logwarn("Motion planning failed.")
        else:
            rospy.logwarn("Unexpected plan structure received.")



if __name__ == '__main__':
    try:
        manipulator_mover = MoveManipulatorToTarget()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("Node terminated.")
    finally:
        roscpp_shutdown()
