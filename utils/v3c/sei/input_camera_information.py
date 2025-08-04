import pandas as pd
from utils.v3c.type    import NalUnitType, SeiPayloadType 
from utils.v3c.sei.sei import Sei

#######################################################################################################
######################## SEI Input Camera Information ################################################# 
#######################################################################################################

class SeiInputCameraInformation(Sei):

    def __init__(self, camera_df=None):
        super().__init__()
        self.sei_payload_type = SeiPayloadType.INPUT_CAMERA_INFORMATION     
  
  #######################################################################################################    

    def write(self, bs, type=None, gof=None):
        self.ici_input_camera_information_cancel_flag = 1 if  gof.camera_df is None else 0
        bs.write_bits(self.ici_input_camera_information_cancel_flag, 1)
        if self.ici_input_camera_information_cancel_flag == 0:

            # set camera information
            self.ici_number_of_camera_minus1   = len( gof.camera_df) - 1
            self.ici_direction_flag            = 1 
            self.ici_quaternion_direction_flag = 1 
            self.ici_general_information_flag  = 1
            self.ici_camera_setting_flag       = 0
            self.ici_image_setting_flag        = 0
            self.ici_image_id                  =  gof.camera_df["imageId"].astype(int).tolist()
            self.ici_camera_id                 =  gof.camera_df["cameraId"].astype(int).tolist()
            self.ici_position_x                =  gof.camera_df["pos.x"].astype(float).tolist()
            self.ici_position_y                =  gof.camera_df["pos.y"].astype(float).tolist()
            self.ici_position_z                =  gof.camera_df["pos.z"].astype(float).tolist()
            self.ici_direction_x               =  gof.camera_df["quat.x"].astype(float).tolist()
            self.ici_direction_y               =  gof.camera_df["quat.y"].astype(float).tolist()
            self.ici_direction_z               =  gof.camera_df["quat.z"].astype(float).tolist()
            self.ici_direction_w               =  gof.camera_df["quat.w"].astype(float).tolist()
            self.ici_focal_length_x            =  gof.camera_df["focal.x"].astype(float).tolist()
            self.ici_focal_length_y            =  gof.camera_df["focal.y"].astype(float).tolist()
            self.ici_camera_manufacturer       =  gof.camera_df["name"].astype(str).tolist()
            self.ici_camera_model              = [""] * len( gof.camera_df)

            # write camera information
            bs.write_uvlc(self.ici_number_of_camera_minus1)
            bs.write_bits(self.ici_direction_flag, 1)
            if self.ici_direction_flag:
                bs.write_bits(self.ici_quaternion_direction_flag, 1)
            bs.write_bits(self.ici_general_information_flag, 1)
            bs.write_bits(self.ici_camera_setting_flag, 1)
            bs.write_bits(self.ici_image_setting_flag, 1)

            for i in range(self.ici_number_of_camera_minus1 + 1):
                bs.write_uvlc(self.ici_image_id[i])
                bs.write_uvlc(self.ici_camera_id[i])
                bs.write_float(self.ici_position_x[i])
                bs.write_float(self.ici_position_y[i])
                bs.write_float(self.ici_position_z[i])
                if self.ici_direction_flag:
                    bs.write_float(self.ici_direction_x[i])
                    bs.write_float(self.ici_direction_y[i])
                    bs.write_float(self.ici_direction_z[i])
                    if self.ici_quaternion_direction_flag:
                        bs.write_float(self.ici_direction_w[i])
                bs.write_float(self.ici_focal_length_x[i])
                bs.write_float(self.ici_focal_length_y[i])

                if self.ici_general_information_flag:
                    bs.write_string(self.ici_camera_manufacturer[i])
                    bs.write_string(self.ici_camera_model[i])

                if self.ici_camera_setting_flag:
                    bs.write_float(self.ici_exposure_time[i])
                    bs.write_float(self.ici_aperture[i])
                    bs.write_uvlc(self.ici_iso_speed[i])
                    bs.write_float(self.ici_exposure_bias[i])
                    bs.write_bits(self.ici_metering_mode[i], 3)
                    bs.write_bits(self.ici_flash_fired_flag[i], 1)
                    bs.write_float(self.ici_focal_length[i])
                    bs.write_string(self.ici_lens_model[i])
                    bs.write_string(self.ici_lens_make[i])

                if self.ici_image_setting_flag:
                    bs.write_uvlc(self.ici_image_width[i])
                    bs.write_uvlc(self.ici_image_height[i])
                    bs.write_bits(self.ici_bits_per_sample[i], 5)
                    bs.write_bits(self.ici_color_space[i], 4)
                    bs.write_bits(self.ici_white_balance_mode[i], 2)
                    bs.write_float(self.ici_saturation_level[i])
                    bs.write_float(self.ici_sharpness_level[i])
                    bs.write_float(self.ici_contrast_level[i])
  
  #######################################################################################################   

    def read(self, bs, type=None, gof=None):
        
        # write camera information
        self.ici_input_camera_information_cancel_flag = bs.read_bits(1)
        if self.ici_input_camera_information_cancel_flag == 0:
            self.ici_number_of_camera_minus1 = bs.read_uvlc()
            self.ici_direction_flag = bs.read_bits(1)
            if self.ici_direction_flag:
                self.ici_quaternion_direction_flag = bs.read_bits(1)
            self.ici_general_information_flag = bs.read_bits(1)
            self.ici_camera_setting_flag = bs.read_bits(1)
            self.ici_image_setting_flag = bs.read_bits(1)

            self.ici_image_id = []
            self.ici_camera_id = []
            self.ici_position_x = []
            self.ici_position_y = []
            self.ici_position_z = []
            self.ici_direction_x = []
            self.ici_direction_y = []
            self.ici_direction_z = []
            self.ici_direction_w = []
            self.ici_focal_length_x = []
            self.ici_focal_length_y = []
            self.ici_camera_manufacturer = []
            self.ici_camera_model = []
            self.ici_exposure_time = []
            self.ici_aperture = []
            self.ici_iso_speed = []
            self.ici_exposure_bias = []
            self.ici_metering_mode = []
            self.ici_flash_fired_flag = []
            self.ici_focal_length = []
            self.ici_lens_model = []
            self.ici_lens_make = []
            self.ici_image_width = []
            self.ici_image_height = []
            self.ici_bits_per_sample = []
            self.ici_color_space = []
            self.ici_white_balance_mode = []
            self.ici_saturation_level = []
            self.ici_sharpness_level = []
            self.ici_contrast_level = []

            for i in range(self.ici_number_of_camera_minus1 + 1):
                self.ici_image_id.append(bs.read_uvlc())
                self.ici_camera_id.append(bs.read_uvlc())
                self.ici_position_x.append(bs.read_float())
                self.ici_position_y.append(bs.read_float())
                self.ici_position_z.append(bs.read_float())

                if self.ici_direction_flag:
                    self.ici_direction_x.append(bs.read_float())
                    self.ici_direction_y.append(bs.read_float())
                    self.ici_direction_z.append(bs.read_float())
                    if self.ici_quaternion_direction_flag:
                        self.ici_direction_w.append(bs.read_float())
                    else:
                        self.ici_direction_w.append(None)
                else:
                    self.ici_direction_x.append(None)
                    self.ici_direction_y.append(None)
                    self.ici_direction_z.append(None)
                    self.ici_direction_w.append(None)

                self.ici_focal_length_x.append(bs.read_float())
                self.ici_focal_length_y.append(bs.read_float())

                if self.ici_general_information_flag:
                    self.ici_camera_manufacturer.append(bs.read_string())
                    self.ici_camera_model.append(bs.read_string())
                else:
                    self.ici_camera_manufacturer.append("")
                    self.ici_camera_model.append("")

                if self.ici_camera_setting_flag:
                    self.ici_exposure_time.append(bs.read_float())
                    self.ici_aperture.append(bs.read_float())
                    self.ici_iso_speed.append(bs.read_uvlc())
                    self.ici_exposure_bias.append(bs.read_float())
                    self.ici_metering_mode.append(bs.read_bits(3))
                    self.ici_flash_fired_flag.append(bs.read_bits(1))
                    self.ici_focal_length.append(bs.read_float())
                    self.ici_lens_model.append(bs.read_string())
                    self.ici_lens_make.append(bs.read_string())
                else:
                    self.ici_exposure_time.append(None)

                if self.ici_image_setting_flag:
                    self.ici_image_width.append(bs.read_uvlc())
                    self.ici_image_height.append(bs.read_uvlc())
                    self.ici_bits_per_sample.append(bs.read_bits(5))
                    self.ici_color_space.append(bs.read_bits(4))
                    self.ici_white_balance_mode.append(bs.read_bits(2))
                    self.ici_saturation_level.append(bs.read_float())
                    self.ici_sharpness_level.append(bs.read_float())
                    self.ici_contrast_level.append(bs.read_float())
                else:
                    self.ici_image_width.append(None)

             # Create camera 
            gof.camera_df = pd.DataFrame({ "imageId":  self.ici_image_id,
                                            "cameraId": self.ici_camera_id,
                                            "pos.x":    self.ici_position_x,
                                            "pos.y":    self.ici_position_y,
                                            "pos.z":    self.ici_position_z,
                                            "quat.w":   self.ici_direction_w,
                                            "quat.x":   self.ici_direction_x,
                                            "quat.y":   self.ici_direction_y,
                                            "quat.z":   self.ici_direction_z,
                                            "focal.x":  self.ici_focal_length_x,
                                            "focal.y":  self.ici_focal_length_y,
                                            "name":     self.ici_camera_manufacturer,
                                        })
            gof.camera_df = gof.camera_df.astype({
                "imageId": int, "cameraId": int,
                "pos.x": float, "pos.y": float, "pos.z": float,
                "quat.w": float, "quat.x": float, "quat.y": float, "quat.z": float,
                "focal.x": float, "focal.y": float,
                "name": str
            })

#######################################################################################################
