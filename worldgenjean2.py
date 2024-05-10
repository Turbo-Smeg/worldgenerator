import numpy as np # Pour diviser la carte en "grid", version glorifiée de listes
from scipy.spatial import Voronoi # Pour les Voronoi diagrams utilisé pour les biomes
import pygame # Interface qui affiche la carte, on peut faire plein dautres choses avec
import noise # Pour le Bruit de Perlin
import tkinter as tk # Interface graphique (GUI) pour faire entrer le "seed"
from tkinter import simpledialog, messagebox, ttk
import sqlite3
import os
import hashlib
from PIL import Image


# Initialiser Pygame
pygame.init()

rel_directory=os.path.dirname(__file__)
filename= 'map_seeds.db'
def initialize_database():
    db_file = (rel_directory+'/'+filename)
    try:
        conn = sqlite3.connect(db_file)
        print("Database connected successfully!")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS map_seeds
                     (id INTEGER PRIMARY KEY, seed TEXT)''')
        conn.commit()
    except sqlite3.Error as e:
        print("Error creating table:", e)
    finally:
        conn.close()

def save_seed_to_database(seed):
    db_file = (rel_directory+'/'+filename)
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("INSERT INTO map_seeds (seed) VALUES (?)", (seed,))
    conn.commit()
    conn.close()

#pour l'ecran de chargement
def show_loading_screen(screen):
    loading_font = pygame.font.Font(None, 36)
    loading_text = loading_font.render("Generating map", True, (0, 0, 0))
    loading_rect = loading_text.get_rect(center=(WORLD_SIZE_X * CELL_SIZE // 2, WORLD_SIZE_Y * CELL_SIZE // 2))

    screen.fill((255, 255, 255))
    screen.blit(loading_text, loading_rect)

    # Points qui apparaissent et disparaissent successivement
    dots = ["", ".", "..", "..."]
    dot_index = 0

    # Condition de fin de chargement (simulée ici)
    loading_complete = False

    # Boucle principale pour afficher les points
    while not loading_complete:
        # Gestion des événements Pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                loading_complete = True  # Arrêt de la boucle si l'utilisateur quitte la fenêtre

        # Affichage du texte avec les points
        loading_text = loading_font.render("Generating map" + dots[dot_index], True, (0, 0, 0))
        screen.fill((255, 255, 255))
        screen.blit(loading_text, loading_rect)
        pygame.display.flip()

        # Mise à jour de l'index du point pour afficher le suivant
        dot_index = (dot_index + 1) % len(dots)

        # Condition de fin de chargement (simulée ici)
        if dot_index == len(dots) - 1:  # Lorsque tous les points ont été affichés
            loading_complete = True

        # Simulation d'une attente entre chaque mise à jour (à remplacer par le vrai chargement)
        pygame.time.wait(500)  # Attendre 500 millisecondes entre chaque mise à jour





# Fonction pr generer une map de bruit d'ambiance. (Bruit perlin)
# J'utilise ca comme la "base" du randomness de la carte un peu
def generate_perlin_noise_map(world_size_x, world_size_y, scale, octaves, persistence, lacunarity, seed):
    world = np.zeros((world_size_x, world_size_y))
    seed_hash = hashlib.md5(seed.encode()).hexdigest()  # Generate MD5 hash of the seed
    seed_int = sum(ord(char) for char in seed_hash)  # Convert hash to integer
    for i in range(world_size_x):
        for j in range(world_size_y):
            world[i][j] = noise.pnoise2(i / scale, j / scale, octaves=octaves, persistence=persistence,
                                        lacunarity=lacunarity, repeatx=1024, repeaty=1024, base=seed_int)
    return world

# Fonction pr generer la météo
def generate_weather_patterns(world_size_x, world_size_y, seed):
    rain_intensity = np.zeros((world_size_x, world_size_y))
    snow_intensity = np.zeros((world_size_x, world_size_y))

    # Generer une map Bruit de Perlin pour la pluie et la neige, effet "hasard" un peu
    # Vous pouvez changer les parametres pour intensifier les effets et vice versa
    rain_map = generate_perlin_noise_map(world_size_x, world_size_y, scale=30, octaves=6, persistence=0.5, lacunarity=2.0, seed=seed)
    snow_map = generate_perlin_noise_map(world_size_x, world_size_y, scale=50, octaves=6, persistence=0.5, lacunarity=2.0, seed=seed)

    # Normalise les valeurs bruit de Perlin rain_map et snow_map pr qu'elles soient dans la plage de 0 à 1
    rain_map = (rain_map - rain_map.min()) / (rain_map.max() - rain_map.min())
    snow_map = (snow_map - snow_map.min()) / (snow_map.max() - snow_map.min())

    # Décider si cette cellule (Biome) devrait avoir une certaine intensité de neige ou de pluie
    for i in range(world_size_x):
        for j in range(world_size_y):
            if snow_map[i][j] > 0.7:  # Neige dans les Tundras
                snow_intensity[i][j] = snow_map[i][j]
            elif rain_map[i][j] > 0.7:  # Pluie dans les forets et oceans
                rain_intensity[i][j] = rain_map[i][j]

    return rain_intensity, snow_intensity

# Fonction pr generer Voronoi diagram
def generate_voronoi_diagram(world_size_x, world_size_y, num_cells, seed, relaxation_iterations=10):
    np.random.seed(hash(seed) % 2**32)
    # Generer les points de cellule pour les biomes
    points = np.random.rand(num_cells, 2) * np.array([world_size_x, world_size_y])

    # Algorithme de relaxation de Lloyd pr amliorer la distribution
    # spatiale des points diagramme de Voronoi (Chat GPT m'a dit dutiliser)
    # Sans ça les biomes sont chaotiques
    for _ in range(relaxation_iterations):
        vor = Voronoi(points)
        for i in range(len(points)):
            region_indices = vor.regions[vor.point_region[i]]
            region_indices = [index for index in region_indices if index != -1]
            region_points = vor.vertices[region_indices]
            centroid = np.mean(region_points, axis=0)
            points[i] = centroid
    # Creer les Voronoi Diagrams
    vor = Voronoi(points)
    return vor

# Attribue les biomes en fonctions des cartes de temperatures et de percipitations (graphique que jai montré dans le groupe)
def assign_biomes(temperature_map, precipitation_map, temperature_thresholds, precipitation_thresholds):
    biomes = np.zeros((len(temperature_map), len(temperature_map[0]), 3))
    for i in range(len(temperature_map)):
        for j in range(len(temperature_map[0])):
            temperature_value = temperature_map[i][j]
            precipitation_value = precipitation_map[i][j]
            biome = determine_biome(temperature_value, precipitation_value, temperature_thresholds, precipitation_thresholds)
            biomes[i][j] = biome
    return biomes

# Détermine le biome en fonction des valeurs de température et de précipitation
# Vous pouvez jouez avec les indexes si vous voulez mais je vous le deconseil mdr
# Ca ma pris une heure pour trouver le "sweet spot" pour donner une apparence naturelle à la carte
# Les valeurs numeriques sont des codes RGB que jai choisi pr la couleur de chaque biome
def determine_biome(temperature_value, precipitation_value, temperature_thresholds, precipitation_thresholds):
    temperature_index = np.searchsorted(temperature_thresholds, temperature_value)
    precipitation_index = np.searchsorted(precipitation_thresholds, precipitation_value)
    if temperature_index == 0:
        if precipitation_index == 0:
            return (0, 51, 153)  # Ocean
        else:
            return (204, 153, 0)  # Desert/Sable
    elif temperature_index == 1:
        if precipitation_index == 0:
            return (204, 153, 0)  # Desert/Sable
        elif precipitation_index == 4:
            return (230, 255, 255)  # Tundra/Neige
        else:
            return (38, 115, 77)  # Foret Boréal
    elif temperature_index == 2:
        if precipitation_index == 0:
            return (38, 115, 77)  # Foret Boréal
        elif precipitation_index == 1:
            return (0, 102, 0)  # Foret Tempéré
        elif precipitation_index == 4:
            return (230, 255, 255)  # Tundra/Neige
        else:
            return (0, 70, 0)  # Foret Tropique
    elif temperature_index == 3:
        if precipitation_index == 0:
            return (0, 102, 0)  # Foret Tempéré
        elif precipitation_index == 3:
            return (0, 70, 0)  # Rainforest
        else:
            return (230, 255, 255)  # Tundra/Neige
    else:
        if precipitation_index == 0:
            return (0, 70, 0)  # Foret Tropique
        else:
            return (230, 255, 255)  # Tundra/Neige

# Fontion pour finalement generer la carte de biomes et de méteo
def generate_world(seed, WORLD_SIZE_X, WORLD_SIZE_Y):
    # Parametres de generation de la carte
    relaxation_iterations = 10 # Nombre d'itérations de l'algo Lloyd
    # pour répartir uniformément les points dans le diagramme de Voronoi.
    scale = 50 # Echelle dans la génération du bruit de Perlin
    # Contrôle la taille des structures dans le bruit généré
    octaves = 6 # Nombre d'octaves utilisé dans la génération du bruit de Perlin
    # Plus d'octaves = plus les détails présents dans le bruit généré
    persistence = 0.5 # Contrôle l'influence de chaque octave sur le résultat final
    lacunarity = 2.0 # Contrôle comment la fréquence des octaves augmente à chaque octave
    temperature_thresholds = [-0.1, -0.05, 0.05, 0.1, 0.25] # Seuils de température déterminent les différentes plages de température pour les biomes
    precipitation_thresholds = [-0.2, -0.15, -0.1, 0.1, 0.25] # Pareil mais pour la percipitation

    # Generer Perlin noise maps pr temperature et precipitation
    temperature_map = generate_perlin_noise_map(WORLD_SIZE_X, WORLD_SIZE_Y, scale, octaves, persistence, lacunarity, seed)
    precipitation_map = generate_perlin_noise_map(WORLD_SIZE_X, WORLD_SIZE_Y, scale, octaves, persistence, lacunarity, seed)

    # Generer motifs de meteo 
    rain_intensity, snow_intensity = generate_weather_patterns(WORLD_SIZE_X, WORLD_SIZE_Y, seed)

    # Attribuer biomes a partir de temp et percip
    biomes = assign_biomes(temperature_map, precipitation_map, temperature_thresholds, precipitation_thresholds)

    return biomes, rain_intensity, snow_intensity


# Fonction dessine la carte avec les biomes et meteo
def draw_world(screen, biomes, rain_intensity, snow_intensity, CELL_SIZE):
    # Dessiner la carte avec le biome attribué
    for i in range(len(biomes)):
        for j in range(len(biomes[0])):
            pygame.draw.rect(screen, biomes[i][j], (i * CELL_SIZE, j * CELL_SIZE, CELL_SIZE, CELL_SIZE))
    # Dessiner la météo
    for i in range(0, len(rain_intensity), 3):
        for j in range(0, len(rain_intensity[0]), 3):
            # Dessiner la pluie
            if rain_intensity[i][j] > 0.7:
                pygame.draw.circle(screen, BLUE, (i * CELL_SIZE, j * CELL_SIZE), 1)
            # Dessiner la neige
            if snow_intensity[i][j] > 0.7:
                pygame.draw.circle(screen, WHITE, (i * CELL_SIZE, j * CELL_SIZE), 1)

# Fonction pour prendre le "seed" de linterface graphique Tkinter (GUI)
def get_seed():
    root = tk.Tk()
    root.withdraw()
    seed = simpledialog.askstring("Enter your Seed", "Enter a string of LETTERS and/or NUMBERS to generate your map.")
    save_seed_to_database(seed)
    return seed


def save_map(biomes, file_format):
    save_dir = os.path.dirname(__file__)
    file_path = os.path.join(save_dir, "map." + file_format.lower())
    biomes_landscape = np.transpose(biomes, axes=(1, 0, 2))
    image = Image.fromarray(biomes_landscape.astype(np.uint8))
    image.save(file_path)
    messagebox.showinfo("Map Saved", f"Map saved successfully as map.{file_format}")

initialize_database()  # Ensure the database is initialized before saving the seed
# Definir les couleurs pour la météo
WHITE = (200, 200, 255) # Neige grise un peu
BLUE = (0, 0, 255) # Pluie bleu foncé

WORLD_SIZE_X = 450 # En nombre de pixel
WORLD_SIZE_Y = 250
CELL_SIZE = 3 # La taille des cellules Voronoi. Plus petites taille = plus de biomes et vice versa
# Parcontre faut aussi prendre en compte la taille de la carte avec (WORLD_SIZE)
seed = get_seed()
screen = pygame.display.set_mode((WORLD_SIZE_X * CELL_SIZE, WORLD_SIZE_Y * CELL_SIZE))
show_loading_screen(screen)
biomes, rain_intensity, snow_intensity = generate_world(seed, WORLD_SIZE_X, WORLD_SIZE_Y)

#Sauvegarder la carte dans un format choisi 
image = Image.fromarray(biomes.astype(np.uint8))

pygame.display.set_caption("Générateur de Carte 4.0")

# Main loop
running = True
# Dessiner la carte
screen.fill((255, 255, 255))
pygame.display.flip()
draw_world(screen, biomes, rain_intensity, snow_intensity, CELL_SIZE)
pygame.display.flip()
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            choice = messagebox.askyesno("Save Map", "Do you want to save the current map?")
            if choice:
                file_format = simpledialog.askstring("Choose File Format", "Enter the file format (PNG, JPG, etc.):")
                if file_format:
                    save_map(biomes, file_format)

# Quit Pygame
pygame.quit()
