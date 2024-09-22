import grpc
import torrent_pb2
import torrent_pb2_grpc
import socket
import uuid

peer_files = []  # Mover esta línea fuera de cualquier función

# Obtener IP local automáticamente
def get_local_ip():
    return socket.gethostbyname(socket.gethostname())

# Conexión con el Web Server
def connect_to_web_server():
    local_ip = get_local_ip()  # Obtener IP local

    # Organización IP del Web Server
    with grpc.insecure_channel('3.85.118.197:50051') as web_server_channel:
        web_server_stub = torrent_pb2_grpc.TorrentServiceStub(web_server_channel)
        response = web_server_stub.GetTorrent(torrent_pb2.TorrentRequest(peer_ip=local_ip))
        tracker_ip = response.tracker_ip
        tracker_port = response.tracker_port
        print(f"Conectado al Web Server. Tracker IP: {tracker_ip}, Tracker Port: {tracker_port}")
        return tracker_ip, tracker_port  # Devolver IP y puerto del tracker

# Conexión con el Tracker
def connect_to_tracker(tracker_ip, tracker_port, peer_files):
    global tracker_channel, tracker_stub
    local_ip = get_local_ip()  # Obtener IP local automáticamente

    # Construir el canal gRPC usando la dirección IP y el puerto recibidos desde el Web Server
    tracker_address = f"{tracker_ip}:{tracker_port}"
    tracker_channel = grpc.insecure_channel(tracker_address)

    # Crear el stub para la conexión con el Tracker
    tracker_stub = torrent_pb2_grpc.TorrentServiceStub(tracker_channel)

    # Convertir peer_files a un diccionario
    file_dict = {file['name']: int(file['size']) for file in peer_files}  # Asegúrate de que el tamaño sea un entero

    # Registrar el peer en el tracker usando su IP local y la lista de archivos
    response = tracker_stub.RegisterPeer(
        torrent_pb2.PeerRequest(
            peer_ip= local_ip,
            files=file_dict
        )
    )

    # Actualizar la lista de archivos si hay archivos actualizados
    if response.updated_files:
        update_peer_files(response.updated_files)
        
    print(f"Peer registered with Tracker: {response.status}, Sent IP: {local_ip}, Tracker Address: {tracker_address}")

    # Enviar automáticamente la lista de archivos del peer al Tracker
    if tracker_stub and peer_files:
        for file in peer_files:
            file_name = file['name']  # Nombre del archivo
            file_size = int(file['size'])  # # Tamaño (dummy)

            tracker_stub.UploadFile(torrent_pb2.UploadFileRequest(peer_ip=local_ip, file_name=file_name, file_size=file_size))
            print(f"File '{file_name}' with size {file_size} uploaded to Tracker.")
    else:
        print("No files to upload or Tracker connection issue.")

def update_peer_files(updated_files):
    global peer_files  # Asegúrate de declarar peer_files como global
    for file in updated_files:
        # Solo agregar archivos que no estén ya en la lista
        if not any(f['name'] == file.file_name for f in peer_files):
            peer_files.append({'name': file.file_name, 'size': file.file_size})
            print(f"Archivo '{file.file_name}' añadido a la lista del peer.")

# Desconexión del tracker
def disconnect_from_tracker():
    global tracker_channel, tracker_stub
    if tracker_stub:  # Solo desconectar si el stub está activo
        try:
            # Enviar solicitud al tracker para eliminar este peer
            response = tracker_stub.UnregisterPeer(
                torrent_pb2.PeerRequest(peer_ip=get_local_ip())
            )
            print(f"Respuesta del tracker: {response.status}")
        except grpc.RpcError as e:
            print(f"Error desconectando del tracker: {e}")
        finally:
            tracker_channel.close()
            tracker_stub = None
            print("Peer desconectado del Tracker y canal cerrado.")
    else:
        print("No conectado al tracker.")

# función de búsqueda
def search_file():
    if tracker_stub:
        file_name = input("Nombre del archivo para obtener: ")
        response = tracker_stub.GetFile(torrent_pb2.GetFileRequest(file_name=file_name))
        # Verifica si hay peers en la respuesta y luego intenta imprimir la IP.
        if response.HasField("peer"):  # Verifica si la respuesta tiene el campo 'peer'
            print(f"Archivo encontrado")
        else:
            print("Archivo no encontrado.")
    else:
        print("No conectado al tracker.")


def run():
    tracker_ip, tracker_port = connect_to_web_server()  # Conectar al Web Server y obtener los datos del tracker

    global tracker_channel, tracker_stub
    tracker_channel = None
    tracker_stub = None

    #peer_files = []  # Lista de archivos del peer. Cada archivo será un diccionario con 'name' y 'size'

    while True:
        print("\nMenu:")
        print("1. Conectar al Tracker")
        print("2. Agregar archivo a la lista del peer")
        print("3. Eliminar archivo de la lista del peer")
        print("4. Ver Lista del Peer")
        print("5. Salir")

        choice = input("Ingresa tu opción: ")

        if choice == '1':
            # Conectar al Tracker con los archivos del peer
            connect_to_tracker(tracker_ip, tracker_port, peer_files)  # Pasa la lista de archivos del peer
            
            # Menú del tracker
            while True:
                print("\nMenú del Tracker:")
                print("1. Buscar archivo")
                print("2. Salir del Tracker")

                tracker_choice = input("Ingresa tu opción: ")

                if tracker_choice == '1':
                    search_file()  # Buscar un archivo en el tracker
                elif tracker_choice == '2':
                    # Desregistrar el peer del tracker y salir al menú principal
                    disconnect_from_tracker()
                    break
                else:
                    print("Opción inválida. Por favor elige una opción válida.")

        elif choice == '2':
            # Agregar archivo a la lista del peer
            file_name = input("Ingresa el nombre del archivo a agregar: ")

            if any(file['name'] == file_name for file in peer_files):
                print(f"El archivo '{file_name}' ya existe en la lista del peer.")
            else:
                while True:  # Bucle para validar la entrada del tamaño del archivo
                    file_size_input = input("Ingrese el tamaño del archivo en MB: ")
                    if file_size_input.isdigit():  # Verifica si es numérico
                        file_size = int(file_size_input)  # Convierte a entero
                        peer_files.append({'name': file_name, 'size': file_size})  # Agregar archivo como diccionario
                        print(f"Archivo '{file_name}' con tamaño {file_size} MB agregado a la lista del peer.")
                        break  # Sale del bucle si la entrada es válida
                    else:
                        print("Error: Solo valores numéricos son permitidos. Intente nuevamente.")


        elif choice == '3':
            # Eliminar archivo de la lista del peer
            file_name = input("Ingresa el nombre del archivo a eliminar: ")
            # Buscar el archivo en la lista de archivos del peer
            file_to_remove = None
            for file in peer_files:
                if file['name'] == file_name:
                    file_to_remove = file
                    break
            
            if file_to_remove:
                peer_files.remove(file_to_remove)
                print(f"Archivo '{file_name}' eliminado de la lista del peer.")
            else:
                print(f"El archivo '{file_name}' no está en la lista.")

        elif choice == '4':
            # Ver lista de archivos del peer
            if peer_files:
                print("\nLista de archivos del peer:")
                for file in peer_files:
                    print(f"- {file['name']} (Size: {file['size']})")
            else:
                print("No tienes archivos en la lista del peer.")
                
        elif choice == '5':
            # Salir del programa
            print("Saliendo...")
            if tracker_stub:
                disconnect_from_tracker()  # Asegura que el peer se desconecte del tracker antes de salir
            break

        else:
            print("Opción inválida. Por favor elige una opción válida.")

if __name__ == '__main__':
    run()