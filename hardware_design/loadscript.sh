#!/bin/bash
. /etc/environment
#
#---------------------------------------------------------------------------------------------
# Create a script in the redpitaya folder that starts the TCPDH_conroller
cat <<EOF > /home/redpitaya/TCPDH.sh
#!/bin/bash
. /etc/environment
#
python3.5  /home/redpitaya/TCPDH_controller.py
EOF

#----------------------------------------------------------------------------------
# create the file that determine the daemon service parameters 
cat <<EOF > /lib/systemd/system/TCPDH.service 
[Unit]
Description = TCPDH server
Requires = redpitaya_nginx.service
After = redpitaya_nginx.service

[Service]
Type=simple
ExecStart=/home/redpitaya/TCPDH.sh

[Install]
WantedBy = basic.target
EOF

#----------------------------------------------------
# Allow the TCPDH.sh to be executable
chmod +x /home/redpitaya/TCPDH.sh

# Start the service
systemctl start TCPDH
systemctl status TCPDH

# enable the service
systemctl enable TCPDH
