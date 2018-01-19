# Plan B Tools #

Some tools to assist the development of Plan B.

## Survey ##
Simple tool to measure and rank the signal strength of wireless access points.

### Installation ###
```
sudo apt install python3-sqlalchemy python3-matplotlib
```

### Collecting Samples ###
```
./survey.py --scan wlp3s0 Büro
```

`wlp3s0` is the WiFi interface to use, `Büro` is the location of my Notebook.


### Displaying Results ###
```
./survey.py --plot
```
