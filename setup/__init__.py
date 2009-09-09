#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, re, os, platform

is64bit = platform.architecture()[0] == '64bit'
iswindows = re.search('win(32|64)', sys.platform)
isosx = 'darwin' in sys.platform
islinux = not isosx and not iswindows
SRC = os.path.abspath('src')
sys.path.insert(0, SRC)
sys.resources_location = os.path.join(os.path.dirname(SRC), 'resources')
sys.extensions_location = os.path.join(SRC, 'calibre', 'plugins')

__version__ = __appname__ = modules = functions = basenames = scripts = None

def initialize_constants():
    global __version__, __appname__, modules, functions, basenames, scripts

    src = open('src/calibre/constants.py', 'rb').read()
    __version__ = re.search(r'__version__\s+=\s+[\'"]([^\'"]+)[\'"]', src).group(1)
    __appname__ = re.search(r'__appname__\s+=\s+[\'"]([^\'"]+)[\'"]', src).group(1)
    epsrc = re.compile(r'entry_points = (\{.*?\})', re.DOTALL).\
            search(open('src/calibre/linux.py', 'rb').read()).group(1)
    entry_points = eval(epsrc, {'__appname__': __appname__})

    def e2b(ep):
        return re.search(r'\s*(.*?)\s*=', ep).group(1).strip()

    def e2s(ep, base='src'):
        return (base+os.path.sep+re.search(r'.*=\s*(.*?):', ep).group(1).replace('.', '/')+'.py').strip()

    def e2m(ep):
        return re.search(r'.*=\s*(.*?)\s*:', ep).group(1).strip()

    def e2f(ep):
        return ep[ep.rindex(':')+1:].strip()

    basenames, functions, modules, scripts = {}, {}, {}, {}
    for x in ('console', 'gui'):
        y = x + '_scripts'
        basenames[x] = list(map(e2b, entry_points[y]))
        functions[x] = list(map(e2f, entry_points[y]))
        modules[x] = list(map(e2m, entry_points[y]))
        scripts[x] = list(map(e2s, entry_points[y]))

initialize_constants()

preferred_encoding = 'utf-8'

def prints(*args, **kwargs):
    '''
    Print unicode arguments safely by encoding them to preferred_encoding
    Has the same signature as the print function from Python 3, except for the
    additional keyword argument safe_encode, which if set to True will cause the
    function to use repr when encoding fails.
    '''
    file = kwargs.get('file', sys.stdout)
    sep  = kwargs.get('sep', ' ')
    end  = kwargs.get('end', '\n')
    enc = preferred_encoding
    safe_encode = kwargs.get('safe_encode', False)
    for i, arg in enumerate(args):
        if isinstance(arg, unicode):
            try:
                arg = arg.encode(enc)
            except UnicodeEncodeError:
                if not safe_encode:
                    raise
                arg = repr(arg)
        if not isinstance(arg, str):
            try:
                arg = str(arg)
            except ValueError:
                arg = unicode(arg)
            if isinstance(arg, unicode):
                try:
                    arg = arg.encode(enc)
                except UnicodeEncodeError:
                    if not safe_encode:
                        raise
                    arg = repr(arg)

        file.write(arg)
        if i != len(args)-1:
            file.write(sep)
    file.write(end)

warnings = []

def get_warnings():
    return list(warnings)

class Command(object):

    SRC = SRC
    RESOURCES = os.path.join(os.path.dirname(SRC), 'resources')
    description = ''

    sub_commands = []

    def __init__(self):
        self.d = os.path.dirname
        self.j = os.path.join
        self.a = os.path.abspath
        self.b = os.path.basename
        self.s = os.path.splitext
        self.e = os.path.exists
        self.real_uid = os.environ.get('SUDO_UID', None)
        self.real_gid = os.environ.get('SUDO_GID', None)
        self.real_user = os.environ.get('SUDO_USER', None)

    def drop_privileges(self):
        if not islinux or isosx:
            return
        if self.real_user is not None:
            self.info('Dropping privileges to those of', self.real_user+':',
                    self.real_uid)
        if self.real_uid is not None:
            os.seteuid(int(self.real_uid))
        #if self.real_gid is not None:
        #    os.setegid(int(self.real_gid))

    def regain_privileges(self):
        if not islinux or isosx:
            return
        if os.geteuid() != 0:
            self.info('Trying to get root privileges')
            os.seteuid(0)
        #if os.getegid() != 0:
        #    os.setegid(0)

    def pre_sub_commands(self, opts):
        pass

    def running(self, cmd):
        from setup.commands import command_names
        self.info('\n*')
        self.info('* Running', command_names[cmd])
        self.info('*\n')

    def run_all(self, opts):
        self.pre_sub_commands(opts)
        for cmd in self.sub_commands:
            self.running(cmd)
            cmd.run(opts)

        self.running(self)
        self.run(opts)

    def add_all_options(self, parser):
        import setup.commands as commands
        self.sub_commands = [getattr(commands, cmd) for cmd in
                self.sub_commands]
        for cmd in self.sub_commands:
            cmd.add_options(parser)

        self.add_options(parser)


    def run(self, opts):
        raise NotImplementedError

    def add_options(self, parser):
        pass

    def clean(self):
        pass

    @classmethod
    def newer(cls, targets, sources):
        '''
        Return True if sources is newer that targets or if targets
        does not exist.
        '''
        if isinstance(targets, basestring):
            targets = [targets]
        if isinstance(sources, basestring):
            sources = [sources]
        for f in targets:
            if not os.path.exists(f):
                return True
        ttimes = map(lambda x: os.stat(x).st_mtime, targets)
        stimes = map(lambda x: os.stat(x).st_mtime, sources)
        newest_source, oldest_target = max(stimes), min(ttimes)
        return newest_source > oldest_target

    def info(self, *args, **kwargs):
        prints(*args, **kwargs)
        sys.stdout.flush()

    def warn(self, *args, **kwargs):
        print '\n'+'_'*20, 'WARNING','_'*20
        prints(*args, **kwargs)
        print '_'*50
        warnings.append((args, kwargs))
        sys.stdout.flush()

def installer_name(ext, is64bit=False):
    if ext == 'exe':
        return 'dist/%s-%s.%s'%(__appname__, __version__, ext)
    if ext == 'dmg':
        if is64bit:
            return 'dist/%s-%s-x86_64.%s'%(__appname__, __version__, ext)
        return 'dist/%s-%s.%s'%(__appname__, __version__, ext)

    ans = 'dist/%s-%s-i686.%s'%(__appname__, __version__, ext)
    if is64bit:
        ans = ans.replace('i686', 'x86_64')
    return ans


