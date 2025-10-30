import math
import os
import sys
import numpy as np
import pandas as pd
import trimesh
from plyfile import PlyData, PlyElement
from utils.common import make_path
from utils.pruning.pruning import calculate_importance_score, prune_by_cdf_threshold

#######################################################################################################

class Pointcloud:

  #######################################################################################################

  def __init__(self, path=None, index=0, num_points=0, verbose=False): 
    self.ply_columns = ['x', 'y', 'z', 'nx', 'ny', 'nz', 'f_dc_0', 'f_dc_1', 'f_dc_2', *[f'f_rest_{i}' for i in range(45)],
                         'opacity', 'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3']
    self.df          = pd.DataFrame(np.zeros((num_points, len(self.ply_columns))), columns=self.ply_columns)
    self.camera_df   = None
    if path is not None:
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
    camera_columns = [ "imageId", "cameraId", "pos.x", "pos.y", "pos.z", "quat.w", "quat.x", "quat.y", "quat.z", "focal.x", "focal.y", "name" ]
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
      raise ValueError(f"PLY file is not valid: can't find 'end_header' in file: {ply_file_path}")

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

      f_rest_cols = [c for c in self.df.columns if c.startswith('f_rest_')]
      num_f_rest = len(f_rest_cols)

      if num_f_rest < 45:
        for j in range(num_f_rest):
          val = self.df[f"f_rest_{j}"].values[i]
          print(f" sh{j:02d} = {val:8.4f}")
      else:
        for j in range(15):
          r = self.df[f"f_rest_{j +  0}"].values[i]
          g = self.df[f"f_rest_{j + 15}"].values[i]
          b = self.df[f"f_rest_{j + 30}"].values[i]
          print(f" sh{j:02d} = {r:8.4f} {g:8.4f} {b:8.4f}")
    if num_points > 0: 
      print("min/max xyz = [%f;%f][%f;%f][%f;%f]" % ( self.df['x'].values.min(), self.df['x'].values.max(), self.df['y'].values.min(),
                                                      self.df['y'].values.max(), self.df['z'].values.min(), self.df['z'].values.max() ))
    sys.stdout.flush()

  #######################################################################################################
  
  def rgb2yuv(self, color_standard, verbose=False):
    if verbose:
      print("Applying RGB to YUV conversion to spherical harmonics")
    # DC components
    if all(f'f_dc_{i}' in self.df.columns for i in range(3)):
      r = self.df['f_dc_0'].values
      g = self.df['f_dc_1'].values
      b = self.df['f_dc_2'].values
      y, cb, cr = color_standard.rgb2yuv_float(r, g, b)
      self.df['f_dc_0'] = y  
      self.df['f_dc_1'] = cb 
      self.df['f_dc_2'] = cr 
    # REST components
    for group_idx in range(0, 15):
      r = self.df[f'f_rest_{group_idx}'].values
      g = self.df[f'f_rest_{group_idx + 15}'].values
      b = self.df[f'f_rest_{group_idx + 30}'].values
      y, cb, cr = color_standard.rgb2yuv_float(r, g, b)
      self.df[f'f_rest_{group_idx}']      = y  
      self.df[f'f_rest_{group_idx + 15}'] = cb 
      self.df[f'f_rest_{group_idx + 30}'] = cr 
      if verbose:
        print(f"  Converted f_rest_{group_idx}, {group_idx + 15}, {group_idx + 30} (RGB -> YUV)")

  #######################################################################################################

  def yuv2rgb(self, color_standard, verbose=False):
    if verbose:
      print("Applying YUV to RGB inverse conversion to spherical harmonics with denormalization")
    # DC components
    if all(f'f_dc_{i}' in self.df.columns for i in range(3)):
      y  = self.df['f_dc_0'].values
      cb = self.df['f_dc_1'].values
      cr = self.df['f_dc_2'].values
      r, g, b = color_standard.yuv2rgb_float(y, cb, cr)
      self.df['f_dc_0'] = r
      self.df['f_dc_1'] = g
      self.df['f_dc_2'] = b
    # REST components
    for group_idx in range(0, 15):
      y  = self.df[f'f_rest_{group_idx}'].values
      cb = self.df[f'f_rest_{group_idx + 15}'].values
      cr = self.df[f'f_rest_{group_idx + 30}'].values
      r, g, b = color_standard.yuv2rgb_float(y, cb, cr)
      self.df[f'f_rest_{group_idx}']      = r
      self.df[f'f_rest_{group_idx + 15}'] = g
      self.df[f'f_rest_{group_idx + 30}'] = b
      if verbose:
        print(f"  Converted f_rest_{group_idx}, {group_idx + 15}, {group_idx + 30} (YUV -> RGB)")

#######################################################################################################

  def normalize_scale_rotation(self, verbose=False):
    s0 = self.df['scale_0'].to_numpy(dtype=np.float64, copy=True)
    s1 = self.df['scale_1'].to_numpy(dtype=np.float64, copy=True)
    s2 = self.df['scale_2'].to_numpy(dtype=np.float64, copy=True)
    qw = self.df['rot_0'].to_numpy(dtype=np.float64, copy=True)
    qx = self.df['rot_1'].to_numpy(dtype=np.float64, copy=True)
    qy = self.df['rot_2'].to_numpy(dtype=np.float64, copy=True)
    qz = self.df['rot_3'].to_numpy(dtype=np.float64, copy=True)
    c = math.sqrt(2.0) / 2.0

    def rot_x(qw,qx,qy,qz, s):      # R = (c, s, 0, 0)
      w2, x2, y2, z2 = c, s, 0.0, 0.0
      w = qw*w2 - qx*x2 - qy*y2 - qz*z2
      x = qw*x2 + qx*w2 + qy*z2 - qz*y2
      y = qw*y2 - qx*z2 + qy*w2 + qz*x2
      z = qw*z2 + qx*y2 - qy*x2 + qz*w2
      return w,x,y,z

    def rot_y(qw,qx,qy,qz, s):      # R = (c, 0, s, 0)
      w2, x2, y2, z2 = c, 0.0, s, 0.0
      w = qw*w2 - qx*x2 - qy*y2 - qz*z2
      x = qw*x2 + qx*w2 + qy*z2 - qz*y2
      y = qw*y2 - qx*z2 + qy*w2 + qz*x2
      z = qw*z2 + qx*y2 - qy*x2 + qz*w2
      return w,x,y,z

    def rot_z(qw,qx,qy,qz, s):      # R = (c, 0, 0, s)
      w2, x2, y2, z2 = c, 0.0, 0.0, s
      w = qw*w2 - qx*x2 - qy*y2 - qz*z2
      x = qw*x2 + qx*w2 + qy*z2 - qz*y2
      y = qw*y2 - qx*z2 + qy*w2 + qz*x2
      z = qw*z2 + qx*y2 - qy*x2 + qz*w2
      return w,x,y,z

    # Decide sign per mask and axis
    def apply_with_sign(qw,qx,qy,qz, axis, mask):
      s = -c
      if axis == 'x': return tuple(np.where(mask, a, b) for a,b in zip(rot_x(qw,qx,qy,qz,s), (qw,qx,qy,qz)))
      if axis == 'y': return tuple(np.where(mask, a, b) for a,b in zip(rot_y(qw,qx,qy,qz,s), (qw,qx,qy,qz)))
      if axis == 'z': return tuple(np.where(mask, a, b) for a,b in zip(rot_z(qw,qx,qy,qz,s), (qw,qx,qy,qz)))

    # Scale sorting + rotation compensation
    m01 = s0 < s1
    s0, s1 = np.where(m01, s1, s0), np.where(m01, s0, s1)
    qw, qx, qy, qz = apply_with_sign(qw,qx,qy,qz, axis='z', mask=m01)
    m02 = s0 < s2
    s0, s2 = np.where(m02, s2, s0), np.where(m02, s0, s2)
    qw, qx, qy, qz = apply_with_sign(qw,qx,qy,qz, axis='y', mask=m02)
    m12 = s1 < s2
    s1, s2 = np.where(m12, s2, s1), np.where(m12, s1, s2)
    qw, qx, qy, qz = apply_with_sign(qw,qx,qy,qz, axis='x', mask=m12)

    # Normalize quaternion after compensations
    n = np.sqrt(qw*qw + qx*qx + qy*qy + qz*qz)
    nz = n > 0
    qw[nz] /= n[nz]
    qx[nz] /= n[nz]
    qy[nz] /= n[nz]
    qz[nz] /= n[nz]
    if np.any(~nz):
      qw[~nz], qx[~nz], qy[~nz], qz[~nz] = 1.0, 0.0, 0.0, 0.0

    # Choose equivalent quaternion with maximal |w|, force w>=0, set w=√2/2
    c0w, c0x, c0y, c0z = qw, qx, qy, qz
    c1w, c1x, c1y, c1z = qx, -qw, -qz, qy
    c2w, c2x, c2y, c2z = qy, qz, -qw, -qx
    c3w, c3x, c3y, c3z = qz, -qy, qx, -qw
    absw = np.stack([np.abs(c0w), np.abs(c1w), np.abs(c2w), np.abs(c3w)], axis=1)
    case_id = np.argmax(absw, axis=1)
    idx = (np.arange(len(case_id)), case_id)
    w = np.stack([c0w, c1w, c2w, c3w], axis=1)[idx]
    x = np.stack([c0x, c1x, c2x, c3x], axis=1)[idx]
    y = np.stack([c0y, c1y, c2y, c3y], axis=1)[idx]
    z = np.stack([c0z, c1z, c2z, c3z], axis=1)[idx]
    neg = w < 0
    w[neg] *= -1.0
    x[neg] *= -1.0
    y[neg] *= -1.0
    z[neg] *= -1.0

    # Fix w = sqrt(2)/2
    scale = np.where(w != 0.0, c / w, 1.0)
    rw = w * scale
    rx = np.clip(x * scale, -1.0, 1.0)
    ry = np.clip(y * scale, -1.0, 1.0)
    rz = np.clip(z * scale, -1.0, 1.0)

    if verbose and len(self.df) > 0:
      nshow = min(3, len(self.df))
      for i in range(nshow):
        print("[normalize] [%3d] sca = (%12.8f, %12.8f, %12.8f) => (%12.8f, %12.8f, %12.8f)" % ( i,
            float(self.df['scale_0'].values[i]), float(self.df['scale_1'].values[i]), float(self.df['scale_2'].values[i]),
            float(s0[i]), float(s1[i]), float(s2[i]) ))
      for i in range(nshow):
        print("[normalize] [%3d] rot = (%12.8f, %12.8f, %12.8f, %12.8f) => (%12.8f, %12.8f, %12.8f, %12.8f)" % ( i,
            float(self.df['rot_0'].values[i]), float(self.df['rot_1'].values[i]), float(self.df['rot_2'].values[i]), 
            float(self.df['rot_3'].values[i]), float(rw[i]), float(rx[i]), float(ry[i]), float(rz[i]) ))

    # Save results
    self.df['scale_0'] = s0
    self.df['scale_1'] = s1
    self.df['scale_2'] = s2
    self.df['rot_0'] = rw
    self.df['rot_1'] = rx
    self.df['rot_2'] = ry
    self.df['rot_3'] = rz

#######################################################################################################        

  def reconstruct_quat(self, verbose=False):
    w = self.df['rot_0'].to_numpy(dtype=np.float64, copy=True)
    x = self.df['rot_1'].to_numpy(dtype=np.float64, copy=True)
    y = self.df['rot_2'].to_numpy(dtype=np.float64, copy=True)
    z = self.df['rot_3'].to_numpy(dtype=np.float64, copy=True)

    # sanitize NaNs/Infs -> 0
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)
    z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)

    # w = sqrt(2)/2 by default
    nw = np.full_like(x, math.sqrt(2.0)/2.0, dtype=np.float64)

    # build and normalize per-point
    Q = np.stack([nw, x, y, z], axis=1)
    n = np.linalg.norm(Q, axis=1)
    nz = np.isfinite(n) & (n > 0)
    Q[nz] /= n[nz, None]
    Q[~nz] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)

    # write back (w,x,y,z)
    self.df['rot_0'] = Q[:,0]
    self.df['rot_1'] = Q[:,1]
    self.df['rot_2'] = Q[:,2]
    self.df['rot_3'] = Q[:,3]

    if verbose and len(self.df) > 0:
      for i in range(min(3, len(self.df))):
        print("[reconstruct] [%3d] q = (%12.8f, %12.8f, %12.8f, %12.8f) => (%12.8f, %12.8f, %12.8f, %12.8f)" %
            (i, w[i], x[i], y[i], z[i], Q[i,0], Q[i,1], Q[i,2], Q[i,3]))

#######################################################################################################

  def pca_sh_ac(self, var_thr, n_comp, verbose=False):
    cols = [c for c in self.df.columns if c.startswith('f_rest_')]
    if not 0 < var_thr <= 1:
      raise ValueError("Variance threshold must be in (0, 1], got %.2f" % var_thr)

    data = self.df[cols].values
    n_pts, n_orig = data.shape

    mean = np.mean(data, axis=0)
    std = np.where((s := np.std(data, axis=0)) == 0, 1, s)
    norm = (data - mean) / std

    _, s_vals, Vt = np.linalg.svd(norm, full_matrices=False)
    cum_var = np.cumsum((s_vals ** 2 / (n_pts - 1)) / np.sum(s_vals ** 2 / (n_pts - 1)))

    n_comp = np.argmax(cum_var >= var_thr) + 1 if n_comp == 0 else min(n_comp, min(n_pts, n_orig))
    comps = Vt[:n_comp]
    reduced = norm @ comps.T

    self.df = self.df.drop(columns=cols)
    for i in range(n_comp):
      self.df['f_rest_%d' % i] = reduced[:, i]

    self.ply_columns = [c for c in self.ply_columns if not c.startswith('f_rest_')] + \
                       ['f_rest_%d' % i for i in range(n_comp)]

    self.pca_result = {'sh_pca_original_dims': n_orig, 'sh_pca_reduced_dims': n_comp,
                       'sh_pca_proj_comps': comps.T, 'sh_pca_mean': mean, 'sh_pca_std': std}

    if verbose:
      print("[PCA SH AC] SH AC coefficients are reduced from %d to %d dims" % (n_orig, n_comp))


  #######################################################################################################

  def inv_pca_sh_ac(self, verbose=False):
    pca_columns = [col for col in self.df.columns if col.startswith('f_rest_')]
    pca_metadata = self.pca_result
    pca_data = self.df[pca_columns].values

    components = pca_metadata['sh_pca_proj_comps']
    mean = pca_metadata['sh_pca_mean']
    std = pca_metadata['sh_pca_std']

    n_reduced = pca_data.shape[1]
    n_orig = components.shape[0]

    reconstructed = (pca_data @ components.T) * std + mean

    self.df = self.df.drop(columns=pca_columns)
    for i in range(reconstructed.shape[1]):
      self.df[f'f_rest_{i}'] = reconstructed[:, i]

    non_sh = [col for col in self.ply_columns if not col.startswith('f_rest_')]
    self.ply_columns = non_sh + [f'f_rest_{i}' for i in range(reconstructed.shape[1])]

    if verbose:
      print("[PCA SH AC] SH AC coefficients are reconstructed to %d from %d dims" % (n_reduced, n_orig))

  #######################################################################################################

  def prune_by_importance(self, cameras, cdf_thr, verbose=False):
    self.df['importance_score'] = calculate_importance_score(self, cameras)
    if cdf_thr < 1.0:
      prune_by_cdf_threshold(self, cdf_thr, verbose)
