#!/usr/bin/python

# PRACTICA FINAL 
# ELISA MERIDA CORONEL Y SOFIA VIDAL URRIZA 


import sys
import subprocess
from lxml import etree
import copy
import time

#Comprobamos si nos han introducido bien el comando
if (len(sys.argv) < 2 or len(sys.argv) > 3):
	sys.stderr.write("Comando incorrecto \n")
	sys.exit(-1)

def crear(numServidores):


	subprocess.call("sudo brctl addbr LAN1", shell=True)
	subprocess.call("sudo brctl addbr LAN2", shell=True)
	subprocess.call("sudo ifconfig LAN1 up", shell=True)
	subprocess.call("sudo ifconfig LAN2 up", shell=True)
	##Configuracion de la red para el Host
	subprocess.call("sudo ifconfig LAN1 10.0.1.3/24 ", shell=True)
	subprocess.call("sudo ip route add 10.0.0.0/16 via 10.0.1.1 ", shell=True)	
	#Creamos la maquina virtual
	crearMV("c1", "LAN1")
	#Utilizamos define porque queremos definir la maquina pero no ejecutarla	
	subprocess.call("sudo virsh define c1.xml", shell=True)

	#Montamos el sistema de ficheros de la maquina virtual c1
	subprocess.call("mkdir /home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/mnt", shell=True)
	subprocess.call("sudo vnx_mount_rootfs -s -r c1.qcow2 mnt", shell=True)
	subprocess.call("echo c1 > mnt/etc/hostname", shell=True) 
	f = open("mnt/etc/network/interfaces", "w")
	f.write("auto lo \n")
	f.write("iface lo inet loopback \n")
	f.write("auto eth0 \n")
	f.write("iface eth0 inet static \n")
	f.write("address 10.0.1.2 \n")
	f.write("netmask 255.255.255.0 \n")
	f.write("network 10.0.1.0 \n")
	f.write("gateway 10.0.1.1 \n")
	f.write("source /etc/network/interfaces.d/*.cfg \n")
	f.close()
	f = open("mnt/etc/sysctl.conf","w")
	f.write("net.ipv4.ip_forward = 1")
	f.close()
	subprocess.call("sudo vnx_mount_rootfs -u mnt", shell=True)


	#Creamos los servidores que nos indiquen con el 2 parametro 
	for servidor in range(1, numServidores+ 1):
		crearMV("s"+ str(servidor), "LAN2")		
		subprocess.call("sudo virsh define s" + str(servidor)+".xml", shell=True)
		subprocess.call("sudo vnx_mount_rootfs -s -r s"+ str(servidor)+".qcow2 mnt", shell=True)
		subprocess.call("echo s"+str(servidor)+" > mnt/etc/hostname", shell=True)
		f = open("mnt/etc/network/interfaces", "w")
		f.write("auto lo \n")
		f.write("iface lo inet loopback \n")
		f.write("auto eth0 \n")
		f.write("iface eth0 inet static \n")
		f.write("address 10.0.2.1"+str(servidor)+"\n")
		f.write("netmask 255.255.255.0 \n")
		f.write("network 10.0.2.0 \n")
		f.write("gateway 10.0.2.1 \n")
		f.write("source /etc/network/interfaces.d/*.cfg \n")
		f.close()

		f = open("/home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/mnt/var/www/html/index.html", "w")
		f.write("s"+str(servidor))
		f.close()

		subprocess.call("sudo vnx_mount_rootfs -u mnt", shell=True)
	
	#Creamos LB y configuramos las LANs
	crearLB()
	
	
	subprocess.call("sudo virsh define lb.xml", shell=True)
	#Montamos el sistema de ficheros de la maquina virtual LB
	subprocess.call("sudo vnx_mount_rootfs -s -r lb.qcow2 mnt", shell=True)
	subprocess.call("echo lb > mnt/etc/hostname", shell=True)
	f = open("mnt/etc/network/interfaces", "w")
	f.write("auto lo \n")
	f.write("iface lo inet loopback \n")
	f.write("auto eth0 \n")
	f.write("iface eth0 inet static \n")
	f.write("address 10.0.1.1\n")
	f.write("netmask 255.255.255.0 \n")
	f.write("network 10.0.1.0 \n")
	f.write("gateway 10.0.1.1 \n")
	
	f.write("auto eth1 \n")
	f.write("iface eth1 inet static \n")
	f.write("address 10.0.2.1\n")
	f.write("netmask 255.255.255.0 \n")
	f.write("network 10.0.2.0 \n")
	f.write("gateway 10.0.2.1 \n")
	f.write("source /etc/network/interfaces.d/*.cfg \n")
	f.close()

	# Configuracion para que LB funcione como Router al arrancar	
	f = open("mnt/etc/sysctl.conf", "w")
	f.write("net.ipv4.ip_forward=1  \n")
	f.close()

	# Balanceador de carga
	numServidores = leerFichero()
	#f = open("/home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/mnt/etc/rc.local", "r")
	f2 = open("/home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/mnt/etc/rc.local", "w")
	f2.write("#!/bin/sh\n")
	# Todo el trafico va al mismo servidor
	#llam = "sudo xr --verbose --server tcp:0:80"
	#Algoritmo Round Robin para la distribucion del trafico
	llam = "sudo xr -dr --verbose --server tcp:0:80"
	
	for servidor in range(1, numServidores+ 1):
		llam += " --backend 10.0.2.1"+str(servidor)+":80"
	
	llam += " --web-interface 0:8001"
	print ("service apache2 stop\n"+llam+"\n")		
	f2.write("service apache2 stop\n"+llam+" &\n")
	#f.close()
	f2.close()

	subprocess.call("sudo vnx_mount_rootfs -u mnt", shell=True)
	subprocess.call("rmdir /home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/mnt", shell=True)


	#Lanzar virt-manager
    	subprocess.call("sudo virt-manager", shell=True)

# Funcion auxiliar para la configuracion de la MV
def crearMV(nombre, LAN):
	#Cargamos el fichero xml
	tree = etree.parse('plantilla-vm-p3.xml')
	
	#Selecciona la imagen a usar
	imagen = tree.find('devices/disk/source')
	imagen.set("file", '/home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/'+nombre+'.qcow2')

	#Cambiamos el nombre de la maquina virtual
	nombreMV = tree.find('name')
	nombreMV.text = nombre

	#Incorpora la MV a su LAN correspondiente
	bridge = tree.find('devices/interface/source')
    	bridge.set("bridge", LAN) 

	#Creamos el xml
	tree.write(open(''+nombre+'.xml', 'w'), encoding = 'UTF-8')

	#Copiamos la imagen de la MV correspondiente
	subprocess.call("qemu-img create -f qcow2 -b cdps-vm-base-p3.qcow2 "+nombre+".qcow2", shell=True)

	#Damos permisos
    	subprocess.call("chmod 777 "+nombre+".xml", shell=True)
   	subprocess.call("chmod 777 "+nombre+".qcow2", shell=True)


#Funcion auxiliar para la configuracion de LB
def crearLB():
	#Cargamos el fichero xml
	tree = etree.parse('plantilla-vm-p3.xml')

	#Selecciona la imagen a usar
	imagen = tree.find('devices/disk/source')
	imagen.set("file", '/home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/lb.qcow2')

	# Cambia el nombre de la VM
    	lb = tree.find('name')
    	lb.text = "lb"

	# Anade el LB a la subred correspondiente
    	interfaz1 = tree.find('devices/interface')
    	interfaz1.find('source').set("bridge", "LAN1") 

	#El LB tiene 2 interfaces (se conecta con 2 LAN distintas)
	interfaz2 = copy.deepcopy(interfaz1)
	interfaz2.find('source').set("bridge", "LAN2")

	#Se incorpora la interfaz (aparece al final)
	tree.find('devices').append(interfaz2)

	#Creamos el xml
	f = open('lb.xml', 'w')
	tree.write(f, encoding = 'UTF-8')
	

	#Copiamos la imagen 
	subprocess.call("qemu-img create -f qcow2 -b cdps-vm-base-p3.qcow2 lb.qcow2", shell=True)

	# Damos permisos
    	subprocess.call("chmod 777 lb.xml", shell=True)
    	subprocess.call("chmod 777 lb.qcow2", shell=True)

def arrancar(mv):
	#Se arrancan todas las MVs si no me pasan parametro
	#print mv
	#print type(None)
	if (mv == type(None)):
		numServidores = leerFichero()
	
		#Arrancamos c1 y mostramos su consola
		subprocess.call("sudo virsh start c1", shell=True)
		subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 'c1' -e 'sudo virsh console c1' &", shell=True)
		

		#Arancamos lb y mostramos su consola
		subprocess.call("sudo virsh start lb", shell=True)
		subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 'lb' -e 'sudo virsh console lb' &", shell=True)	

		#Arrancamos los servidores y mostramos sus consolas
		for servidor in range(1, numServidores+ 1):
			subprocess.call("sudo virsh start s"+ str(servidor), shell=True)
			subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 's"+str(servidor)+"' -e 'sudo virsh console s"+str(servidor)+"' &", shell=True)

	else:
		subprocess.call("sudo virsh start "+ mv, shell=True)
		subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title '"+mv+"' -e 'sudo virsh console "+mv+"' &", shell=True)

def parar(mv):
	if (mv == type(None)):
		subprocess.call("sudo virsh shutdown c1", shell=True)
		subprocess.call("sudo virsh shutdown lb", shell=True)

		numServidores = leerFichero()

		for servidor in range(1, numServidores+ 1):
			subprocess.call("sudo virsh shutdown s"+str(servidor)+"", shell=True)
	else:
		subprocess.call("sudo virsh shutdown "+ mv, shell=True)

def destruir():
	# eliminamos las MV c1 y sus correspondientes ficheros
	subprocess.call("sudo virsh destroy c1", shell=True)
	subprocess.call("sudo virsh undefine c1", shell=True)
	subprocess.call("rm /home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/c1.*", shell=True)
	
	# eliminamos las MV lb y sus correspondientes ficheros	
	subprocess.call("sudo virsh destroy lb", shell=True)
	subprocess.call("sudo virsh undefine lb", shell=True)
	subprocess.call("rm /home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/lb.*", shell=True)

	#eliminamos las MV de los S y sus correspondientes ficheros	
	numServidores = leerFichero()
	

	for servidor in range(1, numServidores+ 1):
		subprocess.call("sudo virsh destroy s"+str(servidor)+"", shell=True)
		subprocess.call("sudo virsh undefine s" + str(servidor), shell=True)
		subprocess.call("rm /home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/s"+str(servidor)+".*", shell=True)
	
	#eliminamos numero.txt
	subprocess.call("rm /home/sofia.vidal.urriza/Documentos/PracticaFinalCDPS/numero.txt", shell=True)


def leerFichero():
	f = open("numero.txt", "r")
	numServidores = int(f.readline())
	f.close()
	return numServidores
	

if sys.argv[1] in ["crear", "arrancar", "parar", "destruir", "monitor"]:
	#print "Primer parametro", sys.argv[1]
	if sys.argv[1] == "crear":
		fnum = open("numero.txt", "w")
		try :
			segundo_param = sys.argv[2]
			if sys.argv[2] in ["1", "2", "3", "4", "5"]:
				fnum.write(sys.argv[2]+"\n")
				fnum.close()
				print "Numero de servidores", sys.argv[2]
			else:
				sys.stderr.write("Numero de servidores incorrecto \n")
				sys.exit(-1)
				
		except Exception: #Mirar si hay excepcion mas concreta
			segundo_param = 2
			fnum.write("2"+ "\n")
			fnum.close()
			print "Numero de servidores por defecto"
		
			
		crear(int(segundo_param))
	
	elif sys.argv[1] == "arrancar":
		try :
		
			if sys.argv[2] in ["c1", "s1", "s2", "s3", "s4", "s5", "lb"]:
				#print type(sys.argv[2])
				arrancar(sys.argv[2])
		except Exception:
			arrancar(type(None))
		
	elif sys.argv[1] == "parar":
		#Aqui se para la maquina virtual
		try :
			#print type(sys.argv[2])
			if sys.argv[2] in ["c1", "s1", "s2", "s3", "s4", "s5", "lb"]:
				#print type(sys.argv[2])
				parar(sys.argv[2])
		except Exception:
			parar(type(None))
		
		print "parar"
	elif sys.argv[1] == "destruir":
		#Aqui se destruye la maquina vitual 
		destruir()
		print "destruir"
	elif sys.argv[1] == "monitor":
		try :
			#print type(sys.argv[2])
			if sys.argv[2] in ["c1", "s1", "s2", "s3", "s4", "s5", "lb"]:
				print sys.argv[2]
				subprocess.call("xterm -rv -sb -rightbar -fa monospace -fs 10 -title 'monitor' -e 'watch -n 5 sudo virsh dominfo " + sys.argv[2]+ "' &", shell=True)
		except Exception:
			sys.stderr.write("Indique la maquina virtual que desee monitorizar \n")
			sys.exit(-1)
	
	 
else:
	sys.stderr.write("Primer parametro incorrecto \n")
	sys.exit(-1)


