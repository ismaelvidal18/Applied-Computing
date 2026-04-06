import carla
import numpy as np
import time
import keyboard
import argparse
import random

'''
Importante al usar sensores:
sensor_tick = fixed_delta_seconds para que el sensor se actualice cada tick del mundo, o un múltiplo de este para reducir la frecuencia de actualización del sensor.
Si no se especifica, el sensor se actualizará tan rápido como sea posible, lo que puede generar una gran cantidad de datos y sobrecargar el sistema.

GETS
    ID = actor.id
    Tipo = actor.type_id
    Transformada = actor.get_transform()
    Ubicación = actor.get_location()
    Velocidad = actor.get_velocity()
''' 

def setup_carla():
    # Se crea una conexión con el servidor de CARLA
    client = carla.Client('localhost', 2000)            # el 2000 indica que se conecta al puerto 2000 del servidor de CARLA
    client.set_timeout(10.0)                            # se establece un tiempo de espera de 10 segundos para las operaciones del cliente

    # La forma más común para experimentos:
    world = client.reload_world(False) 


    # Se configura el mundo de CARLA
    world = client.get_world()                          # se obtiene el mundo actual del servidor de CARLA
    carla_map = world.get_map()                         # se obtiene el mapa del mundo, que contiene información sobre las calles, intersecciones, etc.
    blueprint_library = world.get_blueprint_library()   # se obtiene la biblioteca de planos, que contiene los modelos de vehículos, peatones, etc. disponibles en el mundo
    spectator = world.get_spectator()                   # Se obtiene al espectador

    # Solo para este ejemplo, se elige un vehículo específico (opcional)
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]  # se filtra la biblioteca de planos para obtener el modelo específico del vehículo Tesla Model 3

    # Se generan spawnponits
    spawn_points = carla_map.get_spawn_points()              # se obtienen los puntos de aparición disponibles en el mapa

    print("Mapa cargado: ", carla_map.name)
    print("Vehículo seleccionado: ", vehicle_bp.id)

    # Se configura la sincronía a modo síncrono (asíncrono por defecto)
    settings = world.get_settings()         # se obtiene la configuración actual del mundo para modificarla
    settings.synchronous_mode = True        # se activa el modo síncrono, lo que significa que el mundo solo avanzará cuando se llame a world.tick()
    settings.fixed_delta_seconds = 0.05     # Se configura a 20 FPS (1 segundo / 20 = 0.05 segundos por tick) ó 20Hz
    world.apply_settings(settings)          # se aplican los cambios de configuración al mundo, activando el modo síncrono y estableciendo el tiempo fijo entre ticks

    # Ahora el mundo solo avanzará cuando se llame a world.tick()
    print("Modo síncrono activado. El mundo avanzará a 20 FPS.")

    # =========================
    # Traffic Manager
    # El traffic manager es un módulo de CARLA que se encarga de gestionar el comportamiento del tráfico en la simulación. Permite controlar aspectos como la velocidad, la distancia entre vehículos,
    # las reglas de tráfico, etc. Es especialmente útil para crear escenarios de tráfico realistas y para probar sistemas de conducción autónoma en condiciones variadas.
    # =========================

    tm = client.get_trafficmanager(8000)                    # se obtiene una instancia del Traffic Manager, que se conecta al puerto 8000 del servidor de CARLA
    tm.set_global_distance_to_leading_vehicle(2.5)          # se establece la distancia global que los vehículos deben mantener con el vehículo que tienen delante, en este caso 2.5 metros

    # Se configura al espectador con coordenadas X, Y, Z (en metros)
    spect_location = carla.Location(x=-70.0, y=45.0, z=23.0)

    # Ángulos: pitch (inclinación), yaw (giro horizontal), roll (balanceo)
    spect_rotation = carla.Rotation(pitch=-30.0, yaw=-45.0, roll=0.0)       # se establece la rotación del espectador con un pitch de -30 grados (mirando hacia abajo), un yaw de -45 grados (girado hacia la izquierda) y un roll de 0 grados (sin inclinación lateral)
    spect_transform = carla.Transform(spect_location, spect_rotation)       # se crea una transformación combinando la ubicación y la rotación del espectador, que define su posición y orientación en el mundo de CARLA
    spectator.set_transform(spect_transform)                                # se aplica la transformación al espectador, posicionándolo en el mundo de CARLA según las coordenadas y la orientación especificadas

    # Se crea el vehículo y el tráfico
    #ego_vehicle = world.spawn_actor(vehicle_bp, spawn_points[0])   # se genera el ego-vehicle. El ego-vehicle es el vehículo principal que se controla directamente en la simulación, mientras que los demás vehículos generados se comportarán de manera autónoma según las reglas del tráfico establecidas por el Traffic Manager.
    vehicles = []                                                  # se crea una lista vacía para almacenar los vehículos generados en la simulación
    
    # =========================
    # Spawn de vehículos
    # Se generan 20 vehículos de manera aleatoria en el mapa, utilizando diferentes modelos y puntos de aparición. Cada vehículo se configura para que se comporte de manera autónoma utilizando
    # el Traffic Manager, lo que significa que seguirán las reglas del tráfico y mantendrán la distancia establecida con los vehículos que tengan delante.
    # =========================

    # En vez de generar los vehículos con un ciclo for, se podriá generar con batch lo cuál es lo más eficiente, pero para este ejemplo se hace con un ciclo for para mostrar el proceso de generación de cada vehículo y su configuración individual. En un escenario real, especialmente si se necesitan generar muchos vehículos, sería recomendable utilizar la función apply_batch para optimizar el proceso.
    for i in range(20):

        blueprint = random.choice(blueprint_library.filter("vehicle.*"))    # se selecciona aleatoriamente un plano de vehículo de la biblioteca de planos, filtrando por aquellos que comienzan con "vehicle." para asegurarse de que se seleccionen solo vehículos
        spawn_point = random.choice(spawn_points)                           # se selecciona aleatoriamente un punto de aparición de la lista de puntos de aparición disponibles en el mapa, lo que determina dónde se generará el vehículo en la simulación
        generated_vehicle = world.try_spawn_actor(blueprint, spawn_point)             # se intenta generar un actor (vehículo) en el mundo utilizando el plano seleccionado y el punto de aparición elegido. Si el punto de aparición está ocupado o no es válido, la función devolverá None, lo que se maneja con un condicional para asegurarse de que solo se agreguen a la lista los vehículos que se generaron correctamente

        if generated_vehicle is not None:                             # se verifica si el vehículo se generó correctamente (es decir, no es None) antes de configurarlo para que se comporte de manera autónoma y agregarlo a la lista de vehículos

            generated_vehicle.set_autopilot(True, tm.get_port())      # se configura el vehículo para que se comporte de manera autónoma utilizando el Traffic Manager, lo que significa que seguirá las reglas del tráfico y mantendrá la distancia establecida con los vehículos que tenga delante. Se pasa el puerto del Traffic Manager para asegurarse de que el vehículo se conecte correctamente a él
            vehicles.append(generated_vehicle)                        # se agrega el vehículo a la lista de vehículos generados para poder gestionarlos posteriormente (por ejemplo, para destruirlos al finalizar la simulación)

        print("Vehículos generados:", len(vehicles))


    # Prueba de avance del mundo
    contador = 0
    try:
        while True: # Avanza el mundo de manera indeterminada
            world.tick() # Avanza el mundo un paso
            contador += 1

            '''
            Prueba de control manual del vehículo. Al presionar la tecla 'l'.
            if keyboard.is_pressed('l'):
                control = carla.VehicleControl(throttle=0.5, steer=0.0, brake=0.0)  # se crea un control para el vehículo con un acelerador del 50% y sin dirección
                vehicle.apply_control(control)  # se aplica el control al vehículo
                print("Acelerada")
                for i in range (20, 0, -1):
                    world.tick() # se espera 1 segundo (20 ticks a 20 FPS) para mantener la aceleración durante ese tiempo
                control = carla.VehicleControl(throttle=0.0, steer=0.0, brake=0.0)
                vehicle.apply_control(control)  # se aplica el control al vehículo
                print("Aceleró")
            '''
        
    except KeyboardInterrupt:
        print("Simulación interrumpida por el usuario.")
        print(f"El mundo avanzó {contador} ticks antes de la interrupción.")

    finally:
        print("\nIniciando limpieza...")
        
        # 1. Desactivar modo síncrono (CRÍTICO)
        try:
            settings = world.get_settings()
            settings.synchronous_mode = False
            settings.fixed_delta_seconds = None # Restablece el tiempo variable
            world.apply_settings(settings)
            print("Modo síncrono desactivado. El servidor vuelve a fluir.")
        except Exception as e:
            print(f"Error al restablecer settings: {e}")

        # 2. Destrucción segura de vehículos
        if vehicles:                                                                    # se verifica si hay vehículos en la lista antes de intentar destruirlos para evitar errores
            print(f"Enviando solicitud para destruir {len(vehicles)} vehículos...")     # se imprime un mensaje indicando cuántos vehículos se van a destruir
            client.apply_batch([carla.command.DestroyActor(x) for x in vehicles])       # se envía una solicitud en lote al servidor de CARLA para destruir todos los vehículos generados, utilizando la función DestroyActor para cada vehículo en la lista. Esto es más eficiente que destruirlos uno por uno.
            print("Solicitud de destrucción enviada. Esperando confirmación...")        # se imprime


        print("Limpieza finalizada.")

    
if __name__ == "__main__":    setup_carla()