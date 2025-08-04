import os
import sys
import numpy as np
import pandas as pd
import trimesh 
from plyfile import PlyData, PlyElement
from utils.common import make_path

#######################################################################################################

class Pointcloud:

  #######################################################################################################

  def __init__(self, path=None, index=0, num_points=0, verbose=False): 
    self.ply_columns = ['x', 'y', 'z', 'nx', 'ny', 'nz', 'f_dc_0', 'f_dc_1', 'f_dc_2', *[f'f_rest_{i}' for i in range(45)],
                         'opacity', 'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3']
    self.df          = pd.DataFrame(np.zeros((num_points, len(self.ply_columns))), columns=self.ply_columns)
    self.camera_df   = None
    if path != None:
      self.read(path = path, index = index, verbose = verbose)

  #######################################################################################################

  def read(self, path, index=0, verbose=False):            
    path = make_path( path, index )
    if verbose:
      print("Reading point cloud from ", path)
    sys.stdout.flush()
    if not os.path.exists(path):
      print("Error: %s not exist \n" % path)
      exit(-1)
    else:                
      data     = trimesh.load(path)
      ply_data = data.metadata["_ply_raw"]["vertex"]["data"]
      self.df  = pd.DataFrame(ply_data)   
    self.__read_camera_comments(path)

  #######################################################################################################

  def write(self, path, index=0, ascii=False, verbose=False):
    df_ply = self.df[self.ply_columns].astype(np.float32)
    vertex_el = PlyElement.describe(df_ply.to_records(index=False), "vertex")
    ply_data = PlyData([vertex_el], text=ascii)   
    path = make_path( path, index )
    ply_data.write(path)
    if hasattr(self, "camera_df") and self.camera_df is not None:
      self.__write_camera_comments(path)    
    if verbose:
      print(f"Written {'ASCII' if ascii else 'binary'} PLY to {path}")

  #######################################################################################################

  def __read_camera_comments(self, ply_file_path):
    camera_lines = []
    with open(ply_file_path, 'rb') as f:
      while True:
        line = f.readline()
        if not line:
          break
        line_str = line.decode("utf-8").strip()
        if line_str.startswith("comment camera_position_header"):
            continue  # Ignore header line
        elif line_str.startswith("comment camera_position"):
          camera_lines.append(line_str)
        elif line_str.startswith("end_header"):
          break
    camera_data = []
    for line in camera_lines:
      tokens = line.split()[2:]  # skip 'comment camera_position'
      camera_data.append(tokens)
    camera_columns = [ "imageId", "cameraId", "pos.x", "pos.y", "pos.z", "quat.w", 
                       "quat.x", "quat.y", "quat.z", "focal.x", "focal.y", "name" ]
    self.camera_df = pd.DataFrame(camera_data, columns=camera_columns).astype({
        "imageId": int, "cameraId": int, "pos.x": float, "pos.y": float, "pos.z": float, "quat.w": float, 
        "quat.x": float, "quat.y": float, "quat.z": float, "focal.x": float, "focal.y": float, "name": str })

  #######################################################################################################

  def __write_camera_comments(self, ply_file_path):    
    with open(ply_file_path, 'rb') as f:
      content = f.read()
    end_header_marker = b'end_header\n'
    header_end_index = content.find(end_header_marker)
    if header_end_index == -1:
      raise ValueError("PLY file is not valid : can't find 'end_header' in file: " % ply_file_path )
    header = content[:header_end_index + len(end_header_marker)]
    body   = content[header_end_index + len(end_header_marker):]
    header_line = ( "comment camera_position_header  imageId cameraId"
                    "            pos.x            pos.y            pos.z"
                    "           quat.w           quat.x           quat.y           quat.z"
                    "          focal.x          focal.y             name" )
    comment_lines = [header_line]
    for _, el in self.camera_df.iterrows():
      line = (
        "comment camera_position        " 
        + "{:>8d} ".format(el["imageId"])                   
        + "{:>8d} ".format(el["cameraId"])                  
        + "{:>16.10f} ".format(el["pos.x"])                 
        + "{:>16.10f} ".format(el["pos.y"])
        + "{:>16.10f} ".format(el["pos.z"])
        + "{:>16.10f} ".format(el["quat.w"])
        + "{:>16.10f} ".format(el["quat.x"])
        + "{:>16.10f} ".format(el["quat.y"])
        + "{:>16.10f} ".format(el["quat.z"])
        + "{:>16.10f} ".format(el["focal.x"])
        + "{:>16.10f} ".format(el["focal.y"])
        + "{:>16} ".format(el["name"])                      
      )
      comment_lines.append(line )
    header_str = header.decode("utf-8")
    header_lines = header_str.splitlines()
    updated_header_lines = []
    for i, line in enumerate(header_lines):
        updated_header_lines.append(line)
        if i == 0 and line.strip() == "ply":
            updated_header_lines.extend(comment_lines)

    with open(ply_file_path, 'wb') as f:
        f.write(("\n".join(updated_header_lines) + "\n").encode("utf-8"))
        f.write(body)

  #######################################################################################################

  def print(self, name, num=8):
    num_points = len(self.df)
    print("%s[%6d]:  " % (name, num_points) )
    for i in range(0, min(num_points, num)):
      print(f"point {i:5d}: ")
      print(f" xyz  = {self.df['x'].values[i]:8.4f} {self.df['y'].values[i]:8.4f} {self.df['z'].values[i]:8.4f} ")
      print(f" opa  = {self.df['opacity'].values[i]:8.4f} ")
      print(f" scl  = {self.df['scale_0'].values[i]:8.4f} {self.df['scale_1'].values[i]:8.4f} {self.df['scale_2'].values[i]:8.4f} ")
      print(f" rot  = {self.df['rot_0'].values[i]:8.4f} {self.df['rot_1'].values[i]:8.4f} {self.df['rot_2'].values[i]:8.4f} {self.df['rot_3'].values[i]:8.4f} ")
      print(f" dc   = {self.df['f_dc_0'].values[i]:8.4f} {self.df['f_dc_1'].values[i]:8.4f} {self.df['f_dc_2'].values[i]:8.4f} " )
      for j in range(15):
        print(f" sh{j:02d} = {self.df['f_rest_%d'%(j*3+0)].values[i]:8.4f} {self.df['f_rest_%d'%(j*3+1)].values[i]:8.4f} {self.df['f_rest_%d'%(j*3+2)].values[i]:8.4f} " )
      print(end="\n")
    if num_points > 0: 
      print("min/max xyz = [%f;%f][%f;%f][%f;%f]" % ( self.df['x'].values.min(), self.df['x'].values.max(), self.df['y'].values.min(),
                                                      self.df['y'].values.max(), self.df['z'].values.min(), self.df['z'].values.max() ))

  #######################################################################################################
