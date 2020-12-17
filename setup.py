from setuptools import setup, find_packages
author = "Maarten A. Breddels"
author_email = "maartenbreddels@gmail.com"
license = 'MIT'
url = 'https://www.github.com/maartenbreddels/per4m'

setup(
    author=author,
    author_email=author_email,
    name='per4m',
    description = "Profiling and tracing information for Python using viztracer and perf, the GIL exposed.",
    # version='0.1',
    url=url,
    packages=['per4m'],
    license=license,
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    entry_points={
        'console_scripts': [
            'per4m = per4m.__main__:main',
            'giltracer = per4m.giltracer:main',
            'perf-pyrecord = per4m.record:main',
            'perf-pyscript = per4m.script:main',
            'offgil = per4m.offgil:main',
        ]
    }
)
