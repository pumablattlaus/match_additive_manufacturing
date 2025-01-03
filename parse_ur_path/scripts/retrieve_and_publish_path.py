#! /usr/bin/env python3
import sys
import os
import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
import tf.transformations as tf
import math

# Add the parent directory to the Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import mir_path to retrieve mirX and mirY
from path import ur_path

def apply_transformation(x_coords, y_coords, z_coords, tx, ty, tz, rx, ry, rz):
    transformed_poses = []

    # Convert rotation from Euler angles to a quaternion
    quaternion = tf.quaternion_from_euler(rx, ry, rz)
     
    for i in range(1, len(x_coords)-1):
        pose_stamped = PoseStamped()
        R = tf.quaternion_matrix(quaternion)[:3, :3]

        # Original position + translation
        pose_stamped.pose.position.x = x_coords[i] + R[0, 0] * tx + R[0, 1] * ty + R[0, 2] * tz
        pose_stamped.pose.position.y = y_coords[i] + R[1, 0] * tx + R[1, 1] * ty + R[1, 2] * tz
        pose_stamped.pose.position.z = z_coords[i] + R[2, 0] * tx + R[2, 1] * ty + R[2, 2] * tz
        # the path should always face towards the next point
        orientation = math.atan2(y_coords[i+1] - y_coords[i], x_coords[i+1] - x_coords[i])
        q = tf.quaternion_from_euler(0, 0, orientation)

        pose_stamped.pose.orientation.x = q[0]
        pose_stamped.pose.orientation.y = q[1]
        pose_stamped.pose.orientation.z = q[2]
        pose_stamped.pose.orientation.w = q[3]
        
        # Set the current timestamp
        pose_stamped.header.stamp = rospy.Time.now()
        pose_stamped.header.frame_id = "map"  # Use an appropriate frame

        transformed_poses.append(pose_stamped)
    
    return transformed_poses

def publish_paths():
    rospy.init_node('path_transformer')
    
    # Publishers for the original and transformed paths
    original_pub = rospy.Publisher('/ur_path_original', Path, queue_size=10)
    transformed_pub = rospy.Publisher('/ur_path_transformed', Path, queue_size=10)
    
    # Retrieve the original path
    x_coords = ur_path.toolX()
    y_coords = ur_path.toolY()
    z_coords = ur_path.toolZ()
    
    # Get transformation parameters from ROS params
    tx = rospy.get_param('~tx', 0.0)
    ty = rospy.get_param('~ty', 0.0)
    tz = rospy.get_param('~tz', 0.0)
    rx = rospy.get_param('~rx', 0.0)
    ry = rospy.get_param('~ry', 0.0)
    rz = rospy.get_param('~rz', 0.0)

    # Prepare Path messages
    original_path = Path()
    transformed_path = Path()
    
    # Set frame IDs for paths
    original_path.header.frame_id = "map"  # Use an appropriate frame
    transformed_path.header.frame_id = "map"
    
    # Fill original Path message
    for x, y, z in zip(x_coords, y_coords, z_coords):
        pose_stamped = PoseStamped()
        pose_stamped.pose.position.x = x
        pose_stamped.pose.position.y = y
        pose_stamped.pose.position.z = z  
        pose_stamped.pose.orientation.w = 1.0  # no rotation for original path
        pose_stamped.header.stamp = rospy.Time.now()
        pose_stamped.header.frame_id = "map"
        original_path.poses.append(pose_stamped)
    
    # Transform and fill transformed Path message
    transformed_path.poses = apply_transformation(x_coords, y_coords, z_coords, tx, ty, tz, rx, ry, rz)
    
    rate = rospy.Rate(0.5)  # Publish at 1 Hz
    while not rospy.is_shutdown():
        # Update headers' timestamps
        original_path.header.stamp = rospy.Time.now()
        transformed_path.header.stamp = rospy.Time.now()
        
        # Publish the original and transformed paths
        original_pub.publish(original_path)
        transformed_pub.publish(transformed_path)
        rate.sleep()

if __name__ == '__main__':
    try:
        publish_paths()
    except rospy.ROSInterruptException:
        pass
