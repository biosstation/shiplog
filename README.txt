# Steps to setup shiplog for the first time

# general installs
sudo apt install python3-dev

# install mysql server
sudo apt install mysql-server libmysqlclient-dev
mysql -u root -p -e "create database shiplog"

# setup a virtualenv and activate that virtualenv
sudo apt install virtualenv
mkdir envs
virtualenv --python=/usr/bin/python3 ~/envs/shiplog
source ~/envs/shiplog/bin/activate

# pip packages
pip install django mysqlclient pandas

# get git repo
git clone https://github.com/biosstation/shiplog
cd shiplog

# django setup
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
