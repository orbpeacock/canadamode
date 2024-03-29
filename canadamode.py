import json
import os
from tkinter import Image
import pygame
from pygame.locals import *
import random
import sys
import soundcapture

pygame.init()

os.chdir(os.path.dirname(__file__))

ALL_SPRITES = pygame.sprite.LayeredDirty()
ALL_ELEMENTS = pygame.sprite.LayeredDirty()

SETTINGS_FILE = os.path.join('jsons', 'general_settings.json')

# TODO: Get rid of this and implement loading a target json
DEBUG_FILE = os.path.join('jsons', 'debug_file.json')

CLOCK = pygame.time.Clock()

LAST_MICPERCENT = 0
CURRENT_MIC_PERCENT = 0

# TODO: See if we can make the window transparent. Apparently maybe https://stackoverflow.com/questions/550001/fully-transparent-windows-in-pygames


def save_json(object, file_path):
    fp = open(file_path, 'w')
    json.dump(object, fp, indent=4)
    fp.close()


def load_json(file_path):
    fp = open(file_path, 'r')
    contents = json.load(fp)
    fp.close()
    return contents


def find_element_by_name(name):
    for element in ALL_ELEMENTS:
        if element.name == name:
            return element
    return None


def save_current_settings():
    dict_to_save = {'window_size': DEFAULT_WINDOW_SIZE,
                    'volume_range': DEFAULT_VOLUME_RANGE,
                    'bg_color': DEFAULT_BG_COLOR,
                    'fps': DEFAULT_FPS
                    }
    save_json(dict_to_save, SETTINGS_FILE)


def get_window_size():
    global WINDOW_WIDTH, WINDOW_HEIGHT
    return (WINDOW_WIDTH, WINDOW_HEIGHT)

def trigger_all_mic_listeners():
    for element in ALL_ELEMENTS:
        for event in element.events:
            if event['trigger'] == 'mic':
                event['function'](*event['arguments'])

def relative_mic_percent(raw_level):
    if raw_level < VOLUME_FLOOR:
        return 0
    return min(1, raw_level / VOLUME_CEILING)

"""
Global settings JSON Contains:
Window dimensions
Background color
Volume Range (floor, ceiling)
FPS
"""

"""
JSON Contains:

Window dimensions (optional, else use global)
Background color (optional, else use global)
Volume Range (floor, ceiling) (optional, else use global) TODO: Maybe volume should just be a factor for multiple effects. Eg, imagine volume was a factor for position
FPS (optional else use global)

multiple image_elements, defined by
    name
    image_path
    anchorpoint (optional else center): (%x,%y)
    parentanchor (optional else center):  (%x,%y)
    parentobject (optional else screen): 
    volumelinks (optional): list of (volume:image_path) TODO: Maybe volume should just be a factor for multiple effects. Eg, imagine volume was a factor for position
"""

"""Anatomy of an trigger-action tag:

Possible triggers and arguments:
volume <mic volume level> : <action>
time <elapsed time> : <action>
button_down (ie, one trigger) <KEY> : <action>
button (ie, held) <KEY> : <action>
button_up (ie, one trigger) <KEY> : <action>

Possible actions and arguments
swap_image <image path>
anchor <new anchor>
parent <new parent>
parentanchor <new parent anchor>

(for the future) Tags
Tween <duration>, Crossfade <duration>
"""
# class Triggeraction():
#     def __init__(self, str_description, owner=None):
#         trigger_list, action_list = (i.lower().strip().split() for i in str_description.split(':'))
#         self.trigger = trigger_list[0]
#         self.trigger_args = trigger_list[1:] if len(trigger_list) > 1 else []
#         self.action = action_list[0]
#         self.action_args = action_list[1:] if len(action_list) > 1 else []
#         self.owner = owner

#     def check(self):




# I starting writing a listener class, then realized that if it is remembering functions from other objects, I will
# A) Have unexpected references to those objects and would have to destroy them carefully
# B) Have to code some way of translating the json representation of the object to real pointers
# And if that's not enough, I think it'll actually be easier to just track listens ON the object they're for, so I'm doing that.
# I'll probably just delete this later.

# # A Listener has a list of "listens" which are tuples of [0] A string defining the trigger, [1] A function to run, and [2] A list of arguments
# class Listener():
#     def __init__(self):
#         self.listens = []
    
#     def event(type, details = None):
#         for i in self.listens:
#             if i[0] == type:
#                 arguments = 
#                 i[1]

class Image_element(pygame.sprite.DirtySprite):
    def __init__(self, source_dict=None):
        super().__init__(ALL_SPRITES, ALL_ELEMENTS)
        self.name = ""
        self.image_path = ""
        self.states = []
        self.sockets = []
        self.parent = None
        self.children = []
        self.events = []
        self.anchor_on_parent = [0.5, 0.5]
        self.anchor_on_self = [0.5, 0.5]
        self.offsets = {}
        self.image = pygame.surface.Surface((1, 1)).convert_alpha()
        self.rect = self.image.get_rect()
        if source_dict:
            self.setup_from_dict(source_dict)
        self.apply_position()

    def setup_from_dict(self, dict_arg):
        # A dict can be passed in as a dict or as a path to a json
        if type(dict_arg) == str:
            source_dict = load_json(dict_arg)
        else:
            source_dict = dict_arg
        self.name = source_dict.get('name', self.name)
        self.image_path = source_dict.get('image_path', self.image_path)
        parent_name = source_dict.get('parent_name', None)
        if parent_name:
            self.parent = find_element_by_name(parent_name) if parent_name else None
            if self not in self.parent.children:
                self.parent.children.append(self)

        for s in source_dict.get('states', []):
            self.states.append(State(owner=self, state_data=s))
        self.change_state(0)

        # TODO:
        # When parsing offsets and event arguments, enable the use of special characters
        # e.g.:
        # $mic_percent
        # (maybe even the functions... as in $self.f, $parent.f)
        #


        # TODO: URGH - Offsets and events should be per-state. That'll be a big to-do

        # Offsets should be found in a dict called "offsets"
        # They should each be a string key, and a 2-item list as value
        offsets = source_dict.get('offsets', dict())
        for k in offsets:
            self.offsets[k] = offsets[k]

        # Events should be found in a list called "events"
        # They should be a dict containing:
        #   "trigger":(the trigger to run the function)
        #   "function":(the function to run)
        #   "arguments":(optional) a list of arguments for the function
        events_to_parse = source_dict.get('events', [])
        for e in events_to_parse:
            trigger = e.get('trigger')
            function = e.get('function')
            if function in dir(self):
                function = getattr(self, function)
            else:
                continue
            arguments = e.get('arguments', [])
            self.events.append({"trigger":trigger, "function":function, "arguments":arguments})

    # packages the contents of this Image_element as a dict, ready to write to a json
    # def package_as_dict(self) -> dict:
    #     results_dict = dict()
    #     results_dict['name'] = self.name
    #     results_dict['image_path'] = self.image_path
    #     results_dict['anchorpoint'] = self.anchorpoint
    #     results_dict['parentanchor'] = self.parentanchor
    #     results_dict['parentobject'] = self.parentobject.name if self.parentobject else None
    #     if len(self.children) > 0:
    #         results_dict['children'] = []
    #         for child in self.children:
    #             results_dict['children'].append(child.package_as_dict())
    #     return results_dict

    def get_anchor_target(self):
        if not self.parent or not hasattr(self.parent, 'rect'):
            window_w, window_h = get_window_size()
            return (window_w * self.anchor_on_parent[0], window_h * self.anchor_on_parent[1])
        
        # Try to find a socket with this object's name on it
        sockets_with_matching_name = [s for s in self.parent.sockets if s.child_name.lower() == self.name]
        if len(sockets_with_matching_name) > 0:
            target_socket = sockets_with_matching_name[0]

            x = self.parent.rect.left + \
                self.parent.rect.width * target_socket.position_on_owner[0]
            y = self.parent.rect.top + \
                self.parent.rect.height * target_socket.position_on_owner[1]
        else:
            x = self.parent.rect.left + \
                self.parent.rect.width * self.anchor_on_parent[0]
            y = self.parent.rect.top + \
                self.parent.rect.height * self.anchor_on_parent[1]
        return (x, y)

    def apply_position(self):
        # apply_position() will move the object's rect to where it should be relative to its anchorpoint
        offset = self.calculate_offset()
        parent_x, parent_y = self.get_anchor_target()
        x_offset = self.rect.width * self.anchor_on_self[0] + offset[0]
        y_offset = self.rect.height * self.anchor_on_self[1] + offset[1]
        new_topleft = (parent_x - x_offset, parent_y - y_offset)
        if self.rect.topleft != new_topleft:
            self.rect.topleft = new_topleft
            self.dirty = 1
            for c in self.children:
                c.dirty = 1

    def apply_offset(self, offset_name, offset_value):
        self.offsets[offset_name] = offset_value

    def calculate_offset(self):
        additive_total_x = 0
        additive_total_y = 0
        for k in self.offsets:
            multiplier = 1.0
            if k == 'mic_percent':
                multiplier = CURRENT_MIC_PERCENT
            additive_total_x += self.offsets[k][0] * multiplier
            additive_total_y += self.offsets[k][1] * multiplier
        return additive_total_x, additive_total_y
            

    # TODO: I hate states! Why did I think that was a good idea? Shouldn't I just have multiple Image Elements? I could mass load them if that was my concern
    # Ugh, maybe I'm being hasty. This should be considered carefully before I act on it.
    # Okay, so an Image_Element has 1+ States, not the other way around...
    def change_state(self, new_state_identifier):
        # This command will destroy all pre-existing sockets, change its parent, switch the image, then create the new sockets
        # Accepts as an argument a state object, a name (str), or an index (int)
        if type(new_state_identifier) == int:
            new_state = self.states[new_state_identifier]
        elif type(new_state_identifier) == str:
            new_state = [i for i in self.states if i.name.lower()
                         == new_state.lower()][0]
        else:
            new_state = new_state_identifier

        self.sockets = new_state.sockets

        self.parent = find_element_by_name(new_state.parent_name)
        self.anchor_on_parent = new_state.parent_position_on_parent
        self.anchor_on_self = new_state.parent_position_on_self
        self.image_path = new_state.image_path
        self.image = new_state.image
        self.rect = self.image.get_rect()
        self.scale = new_state.scale

    def update(self):
        # TODO:
        # I want the dirty elements to only update when necessary, but they're updating every frame
        # I should learn more exactly how to deal with dirty sprites / groups 
        #
        # if self.parent and self.parent.dirty:
        #     self.parent.update()
        self.apply_position()
        # print(f"updoot{random.randint(1,6)}")
        # self.dirty = 0

class State():
    # A state is one potential image used for a part of the character along with associated attachment info
    def __init__(self, owner, state_data):
        self.owner = owner
        self.image_path = state_data.get('image_path', "")
        self.scale = state_data.get('image_scale', 1.0)
        # self.image = pygame.image.load(self.image_path)
        # self.image = pygame.transform.rotozoom(self.image, 0.0, self.scale)
        self.image = pygame.transform.rotozoom(pygame.image.load(self.image_path), 0.0, self.scale)
        self.parent_name = state_data.get('parent_name', None)
        socket_data = state_data.get('child_sockets', [])
        self.sockets = [Socket(self.owner, s) for s in socket_data]

        parent_attachment_data = state_data.get('parent_attachment_point', None)
        if parent_attachment_data:
            self.parent_position_on_self = parent_attachment_data.get('position_on_self', [
                0.5, 0.5])
            self.parent_name = parent_attachment_data.get('parent_name', "")
            self.parent_position_on_parent = parent_attachment_data.get('position_on_parent', [
                0.5, 0.5])


class Socket():
    # Sockets are points on a Sprite that other objects will connect to
    def __init__(self, owner, socket_data):
        self.owner = owner
        self.child_name = socket_data.get('child_name', None)
        self.position_on_owner = socket_data.get(
            'position_on_self', [0.5, 0.5])


def load_character_json(json_path):
    image_element_container = pygame.sprite.Group()

    json_contents = load_json(json_path)
    # TODO: Load and apply general settings if found
    for image_element_data in json_contents["image_elements"]:
        new_image_element = Image_element(image_element_data)
        image_element_container.add(new_image_element)


def main():

    CLOCK.tick(FPS)

    ALL_ELEMENTS.update()
    ALL_ELEMENTS.draw(display)

    pygame.display.update()
    eraser_bg = display.copy()
    eraser_bg.fill(BG_COLOR)
    ALL_ELEMENTS.clear(display, eraser_bg)

# Settings and defaults
if os.path.isfile(SETTINGS_FILE):
    loaded_settings = load_json(SETTINGS_FILE)
    settings_loaded = True
else:
    loaded_settings = dict()
    settings_loaded = False

WINDOW_WIDTH, WINDOW_HEIGHT = DEFAULT_WINDOW_SIZE = loaded_settings.get(
    'window_size', (640, 480))
VOLUME_FLOOR, VOLUME_CEILING = DEFAULT_VOLUME_RANGE = loaded_settings.get(
    'volume_range', (0.003, 0.01))
BG_COLOR = DEFAULT_BG_COLOR = loaded_settings.get('bg_color', (0, 255, 0))
FPS = DEFAULT_FPS = loaded_settings.get('fps', 60)

# This ensures that a general settings file exists
save_current_settings()


display = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
display.fill(BG_COLOR)
pygame.display.set_caption("PieGopher Character Animator")

sound_capture = soundcapture.Stream()

# example_character = load_character_json(
#     r"characters/example/example_character.json")

example_character = load_character_json(
    r"characters/Canadian Pie/character.json")

# The main loop
while True:

    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()

    CURRENT_MIC_PERCENT = relative_mic_percent(sound_capture.query())
    # TODO: Make the different volume level detection less dumb
    if int(CURRENT_MIC_PERCENT * 100) != int(LAST_MICPERCENT * 100):
        trigger_all_mic_listeners()
    LAST_MICPERCENT = CURRENT_MIC_PERCENT

    main()
