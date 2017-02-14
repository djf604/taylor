from setuptools import setup, find_packages

setup(
    name='Taylor',
    version='0.1.0',
    description='Tools for OpenStack Swift object storage',
    license='MIT',
    author='Dominic Fitzgerald',
    author_email='dominicfitzgerald11@gmail.com',
    url='https://github.com/djf604/taylor',
    packages=find_packages(),
    entry_points={
        'console_scripts': ['taylor = taylor:execute_from_command_line']
    },
    # install_requires=['PyVCF', 'pyfaidx'], TODO Will include python-synapseclient in the future
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License'
    ]
)
