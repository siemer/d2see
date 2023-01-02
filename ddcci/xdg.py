import os

def base_dirs(varname, split, default):
  e = os.environ.get(varname, '')
  if split:
    e = e.split(':')
  else:
    e = [e]
  e = [*filter(os.path.isabs, e)]  # removes '' as well
  if not e:
    e = [os.path.expanduser(default)]
  return e

def open_config(relpath, mode='r'):
  dirs = base_dirs('XDG_CONFIG_HOME', split=False, default='~/.config')
  if mode == 'r':
    dirs += base_dirs('XDG_CONFIG_DIRS', split=True, default='/etc/xdg')
  for d in dirs:
    fullpath = os.path.join(d, relpath)
    try:
      if mode == 'w':
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
      f = open(fullpath, mode)
    except OSError:
      continue
    else:
      return f
  return open(os.devnull, mode)