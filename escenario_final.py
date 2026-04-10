import carla
import time
import os
import sys

def main():
    # --- 1. Configuración de parámetros ---
    TIEMPO_SIMULACION = 15.0 # Segundos que durará cada clima
    FPS = 20
    DELTA_SECONDS = 1.0 / FPS
    FRAMES_TOTALES = int(TIEMPO_SIMULACION / DELTA_SECONDS) # 300 frames

    # Climas que vamos a evaluar
    climas_a_probar = {
        "1_Despejado": carla.WeatherParameters.ClearNoon,
        "2_Lluvia_Fuerte": carla.WeatherParameters.HardRainNoon,
        "3_Niebla_Densa": carla.WeatherParameters(cloudiness=80.0, precipitation=0.0, fog_density=90.0, fog_distance=2.0)
    }

    # --- 2. Conexión y Modo Síncrono ---
    client = carla.Client('127.0.0.1', 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    
    traffic_manager = client.get_trafficmanager(8000)
    
    # Guardar configuración original para restaurarla al final
    original_settings = world.get_settings()

    try:
        # Aplicar modo determinista
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = DELTA_SECONDS
        world.apply_settings(settings)
        
        traffic_manager.set_synchronous_mode(True)
        traffic_manager.set_random_device_seed(0) # Semilla estricta para rutas idénticas

        blueprint_library = world.get_blueprint_library()
        mapa = world.get_map()
        
        # --- NUEVA LÓGICA: Centrar tráfico donde esté la cámara ---
        espectador = world.get_spectator()
        ubicacion_camara = espectador.get_transform().location
        
        spawn_points = mapa.get_spawn_points()
        # Ordenar de menor a mayor distancia respecto a la cámara
        spawn_points.sort(key=lambda p: p.location.distance(ubicacion_camara))

        if len(spawn_points) < 31:
            print("Error: El mapa no tiene suficientes puntos de aparición para 16 vehículos.")
            sys.exit(1)

        # --- 3. Bucle Principal por Clima ---
        for nombre_clima, parametros_clima in climas_a_probar.items():
            print(f"\n--- Iniciando simulación con clima: {nombre_clima} ---")
            world.set_weather(parametros_clima)

            # REINICIAR LA SEMILLA AQUÍ PARA CADA CLIMA
            traffic_manager.set_random_device_seed(0)
            
            # Crear directorio para guardar la nube de puntos
            output_dir = f'nubes_lidar/{nombre_clima}'
            os.makedirs(output_dir, exist_ok=True)

            actores_simulacion = []

            # 3.1 Spawn del Ego Vehicle
            ego_bp = blueprint_library.find('vehicle.tesla.model3')
            ego_bp.set_attribute('role_name', 'ego')
            ego_transform = spawn_points[0]
            ego_vehicle = world.spawn_actor(ego_bp, ego_transform)
            actores_simulacion.append(ego_vehicle)
            
            # Configurar Ego en Autopilot determinista
            ego_vehicle.set_autopilot(True, traffic_manager.get_port())
            traffic_manager.ignore_lights_percentage(ego_vehicle, 100) # Ignorar semáforos para evitar variaciones por tráfico cruzado

            # 3.2 Spawn del Sensor Lidar
            lidar_bp = blueprint_library.find('sensor.lidar.ray_cast')
            lidar_bp.set_attribute('channels', '64')
            lidar_bp.set_attribute('range', '100')
            lidar_bp.set_attribute('points_per_second', '1000000')
            lidar_bp.set_attribute('rotation_frequency', str(FPS)) # 1 rotación por frame
            
            # Simular impacto del clima en el lidar (ruido/atenuación)
            lidar_bp.set_attribute('dropoff_general_rate', '0.45')
            lidar_bp.set_attribute('dropoff_intensity_limit', '0.8')
            lidar_bp.set_attribute('dropoff_zero_intensity', '0.4')

            lidar_transform = carla.Transform(carla.Location(z=2.4)) # Techo del coche
            lidar = world.spawn_actor(lidar_bp, lidar_transform, attach_to=ego_vehicle)
            actores_simulacion.append(lidar)

            # Callback para guardar .ply. Usamos w=nombre_clima para fijar la variable en la función lambda
            lidar.listen(lambda data, w=nombre_clima: data.save_to_disk(f'nubes_lidar/{w}/%06d.ply' % data.frame))

            # 3.3 Spawn de los 30 vehículos NPC cerca del objetivo
            npc_bp = blueprint_library.filter('vehicle.audi.tt')[0] 
            npcs_spawneados = 0
            indice_punto = 1 # Empezamos en 1 porque el 0 ya lo usó el Ego
            
            while npcs_spawneados < 30 and indice_punto < len(spawn_points):
                npc = world.try_spawn_actor(npc_bp, spawn_points[indice_punto])
                if npc: # Si apareció con éxito y no chocó con otro
                    actores_simulacion.append(npc)
                    npc.set_autopilot(True, traffic_manager.get_port())
                    traffic_manager.ignore_lights_percentage(npc, 100)
                    npcs_spawneados += 1
                
                indice_punto += 1

            # Esperar un poco para que los actores se asienten físicamente
            world.tick()

            # --- 4. Correr la simulación por 15 segundos (300 frames) ---
            print(f"Simulando {TIEMPO_SIMULACION} segundos ({FRAMES_TOTALES} frames)...")
            for frame in range(FRAMES_TOTALES):
                world.tick()
                # Imprimir progreso cada 50 frames
                if (frame + 1) % 50 == 0:
                    print(f"  Frame {frame + 1}/{FRAMES_TOTALES} completado...")

            # --- 5. Limpieza antes del siguiente clima ---
            print("Limpiando actores para el siguiente escenario...")
            # Detener el sensor antes de destruir
            lidar.stop() 
            for actor in actores_simulacion:
                if actor.is_alive:
                    actor.destroy()
            
            # Dar un tick extra para confirmar la destrucción en el servidor
            world.tick()
            time.sleep(1) 

    finally:
        # --- 6. Restaurar CARLA a la normalidad ---
        # Este bloque es vital. Si el script falla a la mitad, esto evita que el simulador se quede congelado.
        print("\nRestaurando configuración original del servidor...")
        world.apply_settings(original_settings)
        traffic_manager.set_synchronous_mode(False)
        print("¡Simulación y recolección de datos terminadas con éxito!")

if __name__ == '__main__':
    main()