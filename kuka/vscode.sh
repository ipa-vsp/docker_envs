  
#!/bin/bash

# Install vscode
#cd /tmp && \
#apt-get update && \ 
apt-get install -y libxss1 libxss-dev && \
#wget -c https://go.microsoft.com/fwlink/?LinkID=760868 -O vscode.deb

apt-get install -y curl apt-transport-https libxss1 libxss-dev libx11-xcb-dev libasound2
curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
install -o root -g root -m 644 microsoft.gpg /etc/apt/trusted.gpg.d/
sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/vscode stable main" > /etc/apt/sources.list.d/vscode.list'
apt-get update
apt-get install -y code # or code-insiders
rm -rf /var/lib/apt/list/*

#cd ~/ && \
#dpkg -i vscode.deb || true && \
#apt -f install -y && \
#dpkg -i vscode.deb

#[Note]
# if install with local user, check ~/.vscode and ~/.config/Code is own by local user
#install package
code --user-data-dir --install-extension ms-vscode.cpptools && \
code --user-data-dir --install-extension ms-python.python && \
code --user-data-dir --install-extension austin.code-gnu-global && \
code --user-data-dir --install-extension xaver.clang-format && \ 
code --user-data-dir --install-extension twxs.cmake && \
code --user-data-dir --install-extension vector-of-bool.cmake-tools && \
code --user-data-dir --install-extension christian-kohler.path-intellisense && \
code --user-data-dir --install-extension visualstudioexptteam.vscodeintellicode && \
code --user-data-dir --install-extension ms-iot.vscode-ros