#######################################################################################################

class Stat:

  def __init__(self, gof = None ):
    self.size     = {} 
    if gof != None:
      self.set(gof)
  
  def add_size(self, name, size ):    
    self.size[name] = self.size.get(name, 0) + size

  def log(self, file=None):
    def print_table(data, title, col1='Name', col2='Bits', show_bytes=True):
        if not data:
            print(f"{title} is empty.\n", file=file)
            return
        names        = list(data.keys())
        bits_vals    = [data[n] for n in names]
        total_bits   = sum(bits_vals)
        if show_bytes:
            bytes_vals   = [b / 8.0 for b in bits_vals]
            total_bytes  = total_bits / 8.0
        percent_vals = [b / total_bits * 100 for b in bits_vals]
        w1 = max(len(col1), *(len(n) for n in names), len("Total"))
        w2 = max(len(col2), *(len(str(b)) for b in bits_vals), len(str(total_bits)))
        if show_bytes:
            w3 = max(len("Bytes"), *(len(f"{b:.2f}") for b in bytes_vals), len(f"{total_bytes:.2f}"))
        w4 = max(len("Percent"), *(len(f"{p:.2f}%") for p in percent_vals), len("100.00%"))
        sep = '-'*w1 + '-+-' + '-'*w2
        if show_bytes:
            sep += '-+-' + '-'*w3
        sep += '-+-' + '-'*w4
        header = col1.ljust(w1) + " | " + col2.rjust(w2)
        if show_bytes:
            header += " | " + "Bytes".rjust(w3)
        header += " | " + "Percent".rjust(w4)
        print(title, file=file)
        print(sep, file=file)
        print(header, file=file)
        print(sep, file=file)
        for i, name in enumerate(names):
            line = name.ljust(w1) + " | " + str(bits_vals[i]).rjust(w2)
            if show_bytes:
                line += " | " + f"{bytes_vals[i]:.2f}".rjust(w3)
            line += " | " + f"{percent_vals[i]:.2f}%".rjust(w4)
            print(line, file=file)
        print(sep, file=file)
        total_line = "Total".ljust(w1) + " | " + str(total_bits).rjust(w2)
        if show_bytes:
            total_line += " | " + f"{total_bytes:.2f}".rjust(w3)
        total_line += " | " + "100.00%".rjust(w4)
        print(total_line, file=file)
        print(file=file)
    print_table(self.size,     "Bitstream Size")
    
#######################################################################################################
