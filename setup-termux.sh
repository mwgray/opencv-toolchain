cd ~
pkg install -y python2 python2-dev clang zip
LDFLAGS=" -lm -lcompiler_rt" pip2 install numpy==1.12

# Package numpy distributables
rm -rf site-packages
mkdir site-packages
cp -r ../usr/lib/python2.7/site-packages/numpy site-packages
cp -r ../usr/lib/python2.7/site-packages/numpy-1.12.0-py2.7.egg-info site-packages
rm -rf termux.zip
zip termux.zip -r site-packages

# Package python library
zip termux.zip ../../files/usr/lib/libpython2.7.so

# Package python files
zip termux.zip -r ../../files/usr/lib/python2.7

# Package python includes
zip termux.zip -r ../../files/usr/include/python2.7

# copy zip to sdcard
cp termux.zip /sdcard/Download
