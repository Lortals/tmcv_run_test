from utils.v3c.type  import V3CExtensionType
from utils.v3c.vps_gsc_extension import VpsGscExtension

#######################################################################################################
################################### vps extension #####################################################
#######################################################################################################

class VpsExtension:

  def __init__(self):
    self.vpsGscExtension = VpsGscExtension()

  def write(self, extensionType, bitstream, gof, verbose=False ):    
    if extensionType == V3CExtensionType.VPS_EXT_PACKED: 
      if verbose:
        print("code vpsExtension VPS_EXT_PACKED ")
    elif extensionType == V3CExtensionType.VPS_EXT_MIV:
      if verbose:
        print("code vpsExtension VPS_EXT_MIV ")
    elif extensionType == V3CExtensionType.VPS_EXT_MIV2:
      if verbose:
        print("code vpsExtension VPS_EXT_MIV2 ")
    elif extensionType == V3CExtensionType.VPS_EXT_VDMC:
      if verbose:
        print("code vpsExtension VPS_EXT_VDMC ")
    elif extensionType == V3CExtensionType.VPS_EXT_GSC:
      if verbose:
        print("code vpsExtension VPS_EXT_GSC ")
      self.vpsGscExtension.write( bitstream, gof )
    else:
      if verbose:
        print("code vpsExtension VPS_EXT_UNSPECIFIED ")
      # for el in data:
      #   bitstream.write_code( el, 8 ) # u(8)
    bitstream.write_length_alignment()

  def read(self, extensionType, bitstream, gof, verbose=False ):    
    if extensionType == V3CExtensionType.VPS_EXT_PACKED: 
      if verbose:
        print("code vpsExtension VPS_EXT_PACKED ")
    elif extensionType == V3CExtensionType.VPS_EXT_MIV:
      if verbose:
        print("code vpsExtension VPS_EXT_MIV ")
    elif extensionType == V3CExtensionType.VPS_EXT_MIV2:
      if verbose:
        print("code vpsExtension VPS_EXT_MIV2 ")
    elif extensionType == V3CExtensionType.VPS_EXT_VDMC:
      if verbose:
        print("code vpsExtension VPS_EXT_VDMC ")
    elif extensionType == V3CExtensionType.VPS_EXT_GSC:
      if verbose:
        print("code vpsExtension VPS_EXT_GSC ")
      self.vpsGscExtension.read( bitstream, gof )
    else:
      if verbose:
        print("code vpsExtension VPS_EXT_UNSPECIFIED ")
      # for el in data:
      #   bitstream.write_code( el, 8 ) # u(8)
    bitstream.read_length_alignment()

#######################################################################################################