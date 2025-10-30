from utils.pointcloud import Pointcloud
from utils.cameras import Cameras

#######################################################################################################

class GroupOfPointclouds:

  #######################################################################################################

  def __init__(self, path: str, num_frames, start_frame=0, verbose=False):
    self.pointclouds = []
    self.cameras = []
    for frame_idx in range(start_frame, start_frame + num_frames) :
      pointcloud = Pointcloud(path=path, index=frame_idx, verbose=verbose)
      self.pointclouds.append(pointcloud)

      camera = Cameras(path, frame_idx, verbose)
      self.cameras.append(camera)

  #######################################################################################################

  def get_min_num_gaussian_in_gof(self):
    return min(len(pc.df) for pc in self.pointclouds)

  #######################################################################################################

  def get_max_num_gaussian_in_gof(self):
    return max(len(pc.df) for pc in self.pointclouds)

  #######################################################################################################

  def get_pointcloud(self, frame_idx):
    return self.pointclouds[frame_idx]

  #######################################################################################################

  def set_pointcloud(self, frame_idx, pointcloud):
    self.pointclouds[frame_idx] = pointcloud

  #######################################################################################################

  def get_camera(self, frame_idx):
    return self.cameras[frame_idx]

  #######################################################################################################

  def get_frame(self, frame_idx):
    return self.get_pointcloud(frame_idx), self.get_camera(frame_idx)

  #######################################################################################################


    