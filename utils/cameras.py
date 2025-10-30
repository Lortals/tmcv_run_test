import os
import struct
import numpy as np

#######################################################################################################

class Cameras:

  def __init__(self, path, index=0, verbose=False):
    self.camtoworlds = []
    self.Ks_dict = {}
    self.image_sizes = {}
    self.verbose = verbose

    if path:
      self.load_from_colmap_files(path, index)

  #######################################################################################################

  def from_camera_df(cls, camera_df):
    camera = cls()

    camtoworlds = []
    for _, row in camera_df.iterrows():
      pos = np.array([row['pos.x'], row['pos.y'], row['pos.z']], dtype=np.float32)
      quat = np.array([row['quat.w'], row['quat.x'], row['quat.y'], row['quat.z']], dtype=np.float32)

      c2w = np.eye(4, dtype=np.float32)
      c2w[:3, :3] = camera.quat_to_rot(quat)
      c2w[:3, 3] = pos
      camtoworlds.append(c2w)

    camera.camtoworlds = np.array(camtoworlds) if camtoworlds else np.array([])

    for _, row in camera_df.iterrows():
      cam_id = int(row['cameraId'])
      fx = float(row['focal.x'])
      fy = float(row['focal.y'])
      # Note: camera_df doesn't contain cx, cy, width, height. May need to modify gsTools to add these values to camera_df
      camera.Ks_dict[cam_id] = np.array([[fx, 0, 0], [0, fy, 0], [0, 0, 1]], dtype=np.float32)

    return camera
  
  #######################################################################################################

  def load_from_colmap_files(self, path, index):
    sparse_path = os.path.join(path, 'colmap_data', f'frame_{index:04d}', 'sparse')
    for ext in ['.bin', '.txt']:
      cam_path = os.path.join(sparse_path, f'cameras{ext}')
      img_path = os.path.join(sparse_path, f'images{ext}')
      if os.path.exists(cam_path) and os.path.exists(img_path):
        if self.verbose:
          print("Reading cameras from ", cam_path)
          print("Reading images from ", img_path)
        (self.read_cameras_bin if ext == '.bin' else self.read_cameras_txt)(cam_path)
        (self.read_images_bin if ext == '.bin' else self.read_images_txt)(img_path)
        return
    raise IOError("No proper COLMAP files found in ", sparse_path)

  #######################################################################################################

  def read_cameras_txt(self, path):
    with open(path, 'r') as f:
      for line in f:
        if line.strip() and not line.startswith('#'):
          parts = line.split()
          cam_id, width, height = int(parts[0]), int(parts[2]), int(parts[3])
          params = [float(p) for p in parts[4:]]
          self.image_sizes[cam_id] = (width, height)
          fx = params[0] if params else 0
          fy = params[1] if len(params) > 1 else fx
          cx = params[2] if len(params) > 2 else width / 2
          cy = params[3] if len(params) > 3 else height / 2
          self.Ks_dict[cam_id] = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32)

  #######################################################################################################

  def read_images_txt(self, path):
    w2c_mats, is_pose = [], True
    with open(path, 'r') as f:
      for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
          if is_pose:
            data = line.split()
            quat, trans = np.array([float(x) for x in data[1:5]]), np.array([float(x) for x in data[5:8]])
            w2c = np.eye(4)
            w2c[:3, :3] = self.quat_to_rot(quat)
            w2c[:3, 3] = trans
            w2c_mats.append(w2c)
          is_pose = not is_pose
    self.camtoworlds = np.linalg.inv(np.stack(w2c_mats))

  #######################################################################################################

  def read_cameras_bin(self, path):
    with open(path, 'rb') as f:
      for _ in range(struct.unpack('Q', f.read(8))[0]):
        cam_id, model_id = struct.unpack('II', f.read(8))
        width, height = struct.unpack('QQ', f.read(16))
        num_params = {0:3, 1:4, 2:5, 3:5, 4:4, 5:5, 6:7, 7:8, 8:10, 9:10, 10:12}.get(model_id, 4)
        params = struct.unpack(f'{num_params}d', f.read(8 * num_params))
        self.image_sizes[cam_id] = (width, height)
        fx = params[0] if params else 0
        fy = params[1] if len(params) > 1 else fx
        cx = params[2] if len(params) > 2 else width / 2
        cy = params[3] if len(params) > 3 else height / 2
        self.Ks_dict[cam_id] = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32)

  #######################################################################################################

  def read_images_bin(self, path):
    w2c_mats = []
    with open(path, 'rb') as f:
      for _ in range(struct.unpack('Q', f.read(8))[0]):
        struct.unpack('I', f.read(4))
        quat, trans = np.array(struct.unpack('4d', f.read(32))), np.array(struct.unpack('3d', f.read(24)))
        struct.unpack('I', f.read(4))
        b''.join(c for c in iter(lambda: f.read(1), b'\x00'))
        f.read(24 * struct.unpack('Q', f.read(8))[0])
        w2c = np.eye(4)
        w2c[:3, :3] = self.quat_to_rot(quat)
        w2c[:3, 3] = trans
        w2c_mats.append(w2c)
    self.camtoworlds = np.linalg.inv(np.stack(w2c_mats))

  #######################################################################################################

  def quat_to_rot(self, q):
    qw, qx, qy, qz = q
    return np.array([
      [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qw*qz), 2*(qx*qz + qw*qy)],
      [2*(qx*qy + qw*qz), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qw*qx)],
      [2*(qx*qz - qw*qy), 2*(qy*qz + qw*qx), 1 - 2*(qx**2 + qy**2)]
    ])

  #######################################################################################################
