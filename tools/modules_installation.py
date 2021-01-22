import sys, subprocess

python_modules = [('networkx', None, None),
                  ('numpy', None, None),
                  ('matplotlib', None, None),
                  ('scikit-learn', 'sklearn', None),
                  ('pyyaml', 'yaml', None),
                  #########################
                  # behavioral-model: dependency installed for python 3, not still python 2, need it for python 2
                  ('thrift', None, None),
                  ('nnpy', None, None),
                  #########################
                  ('scapy', None, '2.4.3')]  # asynchronous sniffing supported since scapy v2.4.3


def install_python_module(python_module, import_name=None, version=None):
    try:
        import pip
        from pip import main as pip_install
    except:
        raise Exception('pip not installed')

    try:
        import importlib
        importlib.import_module(python_module if import_name is None else import_name)

        if version is not None:
            try:
                python_module_version = sys.modules[python_module if import_name is None else import_name].__version__
            except:
                python_module_version = subprocess.check_output('pip freeze | grep {}'.format(python_module), shell=True).split('==')[1].strip()
            if python_module_version != version:
                raise ImportError
    except ImportError:
        print('pip: installing missing module ({})'.format(python_module))
        pip_install(['install', python_module if version is None else '{}=={}'.format(python_module, version), '-qqq'])
