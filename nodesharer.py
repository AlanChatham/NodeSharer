"""
MIT License

Copyright (c) 2021 Node Sharer Devs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import bpy # type: ignore
import pprint
import json
import inspect
import zlib
import base64
import os
from bpy.props import StringProperty, BoolProperty # type: ignore
from bpy_extras.io_utils import ImportHelper, ExportHelper # type: ignore

# from . import compfixer


def dump(obj):
    """Dumps class variables and functions for debug"""
    print('\n')
    for attr in dir(obj):
        if hasattr(obj, attr):
            tmp = getattr(obj, attr)
            if inspect.isclass(obj):
                print("recursing")
                dump(attr)
            else:
                print("obj.%s = %s" % (attr, tmp))


class NS_node:
    """Stores a node
        Member variables:
            self.properties - a dict of property-value pairs, like "location" -> dict of location data
            self.blender_source_node - a blender node object
            self.nodetree_inside_node - None, unless this is a node that contains another tree
            self.name - the name of the node
        Used in preparation for JSONifying or before being added to a node tree"""

    # Blender nodes have a lot of data, and we only want some of it,
    #  these lists help us only save what is relevant 
    _prop_common = ('name', 'bl_idname', 'inputs', 'outputs', 'location')  # always saved properties

    _prop_optional = {'hide': False, 'label': '', 'mute': False, 'parent': None, 'select': False, 'show_options': True,
                      'show_preview': False, 'show_texture': False,
                      'use_custom_color': False}  # Saved if they are not default valued

    _prop_common_ignored = ('bl_description', 'bl_icon', 'bl_label', 'type', 'bl_height_default', 'bl_height_max',
                            'bl_height_min', 'bl_rna', 'bl_static_type', 'bl_width_default',
                            'bl_width_max', 'bl_width_min', 'draw_buttons', 'draw_buttons_ext',
                            'input_template', 'texture_mapping', 'uv_map', 'color_mapping',
                            'internal_links', 'is_registered_node_type', 'output_template', 'poll', 'poll_instance',
                            'rna_type', 'socket_value_update', 'update', 'image_user', 'dimensions',
                            'width_hidden', 'interface', 'object', 'text', 'color', 'height', 'image',
                            'width', 'filepath')  # never saved cus they are useless or created with the node by blender

    def __init__(self, node, *args, **kwargs):
        self.properties = {}
        self.blender_source_node = node

        # Store the node properties into self.properties,
        #  self.nodetree_inside_node is used in case this
        #  node is actually a node tree with more nodes inside it
        self.nodetree_inside_node = self.store_blender_node_properties()
        self.name = self.properties['name']

    def store_blender_node_properties(self):
        """Store a node's properties  - returns the sub-tree
            if this node is actually a sub-tree as an NS_group
        """
        to_return = None
        tmp_prop = {}
        # fill the dict tmp_prop with all the node's properties
        for attr in dir(self.blender_source_node):
#            print(attr, end=" : ")  #DEBUG
            # No idea why this is wrapped like this,
            #  but don't see the harm?
            ### AHH we do this to make it iterable
            if hasattr(self.blender_source_node, attr):
#                print(attr) #DEBUG
                tmp_prop[attr] = getattr(self.blender_source_node, attr)
#            else: #DEBUG
#                print("!!!!!!!!!!!!!!!!!") #DEBUG

        for k in tmp_prop:  # for key in node properties
            if k in self._prop_common:
                if k == 'inputs':
                    tmp_inputs = {}
                    for index, node_inputs in enumerate(self.blender_source_node.inputs):
                        # key = '' + str(idx)
                        key = index
                        # save default values a node has
                        if hasattr(node_inputs, 'default_value') == False:
#                            print (node_inputs.name + " has no default")
                            continue
                        if node_inputs.default_value == None:
#                            print (node_outputs.name + " default is None")
                            continue
                        if type(node_inputs.default_value) == str:
                            tmp_inputs[key] = node_inputs.default_value
                        else:
                            try:
                                try:
                                    # default values, like if you manually set a Transform
                                    #  geo node to specific values, are also inputs/outputs
                                    tmp_inputs[key] = round(node_inputs.default_value, 5)
                                except:
                                    tmp_inputs[key] = tuple(round(tmp_v, 5) for tmp_v in node_inputs.default_value)
                            except Exception as e:
    #                            print('input ' + str(index) + ' not default value')
    #                            print(e)
                                # tmp_inputs[key] = ''
                                pass
                    if tmp_inputs != {}:
                        self.properties[k] = tmp_inputs

                elif k == 'outputs':
                    tmp_outputs = {}
                    output_default_value = {}
                    for index, node_outputs in enumerate(self.blender_source_node.outputs):
                        # key = '' + str(idx)
                        key = index
                        # save default values a node has
                        if hasattr(node_outputs, 'default_value') == False:
                #            print (node_outputs.name + " has no default")
                            continue
                        if node_outputs.default_value == None:
                #            print (node_outputs.name + " default is None")
                            continue
                        if type(node_outputs.default_value) == str:
                            tmp_outputs[key] = node_outputs.default_value
                        else:
                            try:
                                try:
                                    output_default_value[key] = round(node_outputs.default_value, 5)
                                except:
                                    print("got here")
                                    try:
                                        output_default_value[key] = tuple(round(tmp_v, 5) for tmp_v in node_outputs.default_value)
                                    except AttributeError:
                                        print('now here')
                                        pass
                            except AttributeError:
                                print('and lastly here')
                                pass

                        try:
                            # print('Dumping ' + key)
                            if node_outputs.is_linked:
                                tmp_links = {}
                                for node_links in node_outputs.links:
                                    s = node_links.to_socket.path_from_id()
                                    s = int((s.split('inputs['))[1].split(']')[0])
                                    tmp_link_name = node_links.to_node.name
                                    if tmp_link_name in tmp_links:
                                        try:
                                            tmp_links[tmp_link_name] = tmp_links.get(tmp_link_name) + (s,)
                                        except:
                                            tmp_links[tmp_link_name] = (tmp_links.get(tmp_link_name),) + (s,)
                                    else:
                                        tmp_links[tmp_link_name] = s

                                tmp_outputs[key] = tmp_links
                        except:
                            tmp_outputs[node_outputs] = str(node_outputs.links)
                    if tmp_outputs != {}:
                        self.properties[k] = tmp_outputs
                    if output_default_value != {}:
                        self.properties['out_dv'] = output_default_value

                elif k == 'location':
                    try:
                        self.properties['location'] = (round(tmp_prop[k][0]), round(tmp_prop[k][1]),)
                    except:
                        print("location/vector dump failed")

                else:
                    self.properties[k] = tmp_prop[k]

            elif k in self._prop_optional:
                value = tmp_prop[k]
                if value != self._prop_optional[k]:
                    if k == 'parent':
                        self.properties[k] = value.name
                        continue
                    self.properties[k] = value
                    if k == 'use_custom_color':
                        self.properties['color'] = tuple(round(tmp_v, 5) for tmp_v in tmp_prop['color'])

            elif k in self._prop_common_ignored:  # Sort out all unwanted properties
                continue

            elif k[:1] == '_':  # Sort out double underscore
                continue

            elif k == 'node_tree':
                try:
                    self.properties['node_tree'] = tmp_prop[k].name
                    to_return = {tmp_prop[k].name: NS_group(tmp_prop[k])}
                except Exception as e:
                    print('Group node tree failed')
                    print(e)
            elif k == 'color_ramp':
                tmp_cr = {}
                tmp_elements = {}

                tmp_cr['color_mode'] = tmp_prop[k].color_mode
                tmp_cr['hue_interpolation'] = tmp_prop[k].hue_interpolation
                tmp_cr['interpolation'] = tmp_prop[k].interpolation

                for element in tmp_prop[k].elements:
                    tmp_elements[round(element.position, 5)] = tuple(round(tmp_v, 5) for tmp_v in element.color)
                tmp_cr['elements'] = tmp_elements
                self.properties[k] = tmp_cr

            elif k == 'mapping':
                tmp_mapping = {}
                tmp_curves = {}

                tmp_mapping['clip_max_x'] = tmp_prop[k].clip_max_x
                tmp_mapping['clip_max_y'] = tmp_prop[k].clip_max_y
                tmp_mapping['clip_min_x'] = tmp_prop[k].clip_min_x
                tmp_mapping['clip_min_y'] = tmp_prop[k].clip_min_y

                tmp_mapping['extend'] = tmp_prop[k].extend
                tmp_mapping['tone'] = tmp_prop[k].tone
                tmp_mapping['use_clip'] = tmp_prop[k].use_clip

                for idc, curve in enumerate(tmp_prop[k].curves):
                    tmp_points = {}
                    for idp, point in enumerate(curve.points):
                        tmp_points[idp] = (round(point.location[0], 5), round(point.location[1], 5),)
                    tmp_curves[idc] = tmp_points
                tmp_mapping['curves'] = tmp_curves

                self.properties[k] = tmp_mapping

            else:  # Catch all. for the random named attributes
                if isinstance(tmp_prop[k], (int, str, bool, float)):
                    self.properties[k] = tmp_prop[k]
                else:
                    try:
                        self.properties[k] = tmp_prop[k].name
                    except:
                        pass
                        # self.properties[k] = 'object'

        return to_return  # Return to pass through

    def print_prop(self):
        pprint.pprint(self.properties)
        print('\n')

    def toJSON(self):
        return self.properties
        # return json.dumps(self.properties, sort_keys=True, indent=4)


class NS_nodetree:
    """stores NS_nodes's"""
    #TODO: figure out what can be extracted from NS_material
    #      to generalize that
    #      Also probably wrap all of NS_mat_constructor in here?
    groups = {}

    def __init__(self, blender_nodetree = None):
        # some data members, filled out by constructor methods
        self.name = None
        self.nodetree_type = None
        self._nodes = {}
        self.groups = {}
        # Node trees hold information about their inputs and outputs,
        #  this used to be held in an input and output dict like a node,
        #  but in 4.0 they changed this to be in NodeTree.NodeTreeInterface
        self.interface = None
        if (blender_nodetree != None):
            self.construct_from_blender_nodetree(blender_nodetree)
        

    def construct_from_blender_nodetree(self, blender_nodetree : bpy.types.NodeTree):
        self.name = blender_nodetree.name
        self.nodetree_type = blender_nodetree.bl_idname 
        self._nodes = {}
        self.populate_nodetree(blender_nodetree)
        # Let's just store a reference to the underlying tree's interface
        self.interface = blender_nodetree.interface
        

    def add_node(self, blender_node):
        """Add node to this NS_nodetree from a blender node object"""
        n = NS_node(blender_node)
        self._nodes[n.name] = n

        # A node can be an entire node tree itself, if it is,
        #  add the node tree 
        if n.nodetree_inside_node is not None:
            k, v = n.nodetree_inside_node.popitem()
            self.groups[k] = v
    
    
    def populate_nodetree(self, blender_node_tree):
        """Fill the NS_nodetree from blender data"""
        for node in blender_node_tree.nodes:
            self.add_node(node)

    def make_dict(self):
        """Returns a dictionary of all the nodetree's nodes
            as (NS_node)node -> (dict)node property dictionary pairs
        """
        tmp_dict = {}
        for nk, nv in self._nodes.items():
            tmp_dict[nk] = nv.properties
        return tmp_dict

    def print_tree(self):
        """Print tree"""
        for k in self._nodes:
            print('\n')
            self._nodes[k].print_prop()
        # pprint.pprint(self._nodes)
        # print('\n')

    def dumps_JSON(self, d):
        """Indented SON for viewing"""
        # for node in self._nodes:
        #     print(node.toJSON())
        return json.dumps(d, default=lambda o: o.properties, indent=2)

    def dump_JSON(self, d):
        """Unindented json for compressing"""
        return json.dumps(d, separators=(',', ':'), default=lambda o: o.properties)
        # return json.dumps(d, separators=(',', ':'), default=lambda o: o.toJSON())

    def dumps_nodetree_JSON(self):
        # All trees have name, type, and nodes
        nodetree_dict_to_jsonify = {'name': self.name,
                         'type': self.nodetree_type,
                         'nodes': self._nodes}
        # If a tree contains node groups (subtrees), add those too
        if self.groups != {}:
            nodetree_dict_to_jsonify['groups'] = self.groups
        # Add interface data
        interface_info = self.get_interface_info()
        if interface_info != {}:
            nodetree_dict_to_jsonify['interface'] = interface_info
        #print('JSON dump of nodes')
        return self.dumps_JSON(nodetree_dict_to_jsonify)
    
    def get_interface_info(self):
        """ We're storing a direct link to the blender NodeTreeInterface for this node tree
                so we need to be able to extract the info we need for reconstruction
                while not bulking up on useless data, same as we do in add_node, just
                we're keeping things more dynamic here
        """
        # properties to save even when they're the default, which we normally don't save
        _prop_always_save = ('position')
        _prop_common_ignored = ('index','rna_type', 'bl_rna', 'bl_socket_idname',
                                'interface_items')
        # iterface_items above is where a panel stores it's children
        #  we already have parent data from each node, so we don't need that
        
        interface_dict_to_return = {}

        interface_item : bpy.types.NodeTreeInterfaceItem
        for interface_item in self.interface.items_tree:

            # Get an iterable dict of our interface item properties
            interface_properties = {}
            
            for attribute in dir(interface_item):
                # We don't want functions
                if callable(getattr(interface_item, attribute)):
                    continue
                # nor pythonic builtins
                if attribute[:1] == '_': 
                    continue
                # nor some other automatic attributes
                if attribute in _prop_common_ignored:
                    continue
                # nor if it's None
                if getattr(interface_item, attribute) == None:
                    # print (attribute + " WAS None, DIDN'T STORE")
                    continue
                # and don't store something if it has the default value
                if attribute not in _prop_always_save:
                    if hasattr(interface_item.bl_rna.properties[attribute], 'default'):
                        # print (attribute + " has a default: ", end="")
                        # print (str(interface_item.bl_rna.properties[attribute].default))
                        # print ("Is it's value, " + str(getattr(interface_item, attribute)) +
                        #        ", the same?", end="")
                        if interface_item.bl_rna.properties[attribute].default == getattr(interface_item, attribute):
                            continue
                
                # else, down here, since all the above blocks end in a continue
                interface_properties[attribute] = getattr(interface_item, attribute)

            print (interface_properties)
            # Now do some processing for some special cases
            for property in interface_properties:
                # We need to store parents by persistent_uid instead of an object link
                if property == 'parent':
                    interface_properties['parent'] = interface_properties['parent'].persistent_uid
                # Sometimes data comes in a list, like a vector, so deal with that 
                if not isinstance(interface_properties[property], (int, str, bool, float)):
                    try:
                        interface_properties[property] = tuple(interface_properties[property])
                        print("Saved " + property + " as a tuple, " + str(interface_properties[property]))
                    except Exception as e:
                        print(e)
                        print("Couldn't save " + property + " on it's own, trying to save it data.name_full")
                        
                        try:
                            interface_properties[property] = interface_properties[property].name_full
                            print("Saved " + property + " as a name, " + interface_properties[property])
                        except Exception as e:
                            print(e)
                            interface_properties[property] = None
                            print("Couldn't save " + property + " as a name, either, so saving it as None")
                            


                        
                
            
            interface_dict_to_return[interface_item.name] = interface_properties

        return interface_dict_to_return
    
    
    def construct_from_JSON(self, JSON_input):
        # Get our JSON data into an object
        input_data = json.loads(JSON_input)
        # We could probably load this directly in, but this
        #  explicitly sets the class variables from the JSON data
        self.name = input_data.get("name")
        self.type = input_data.get("type")
        self._nodes = input_data.get("nodes")
        self.groups = input_data.get("groups")
        self.create_full_blender_nodetree()

    
    def create_full_blender_nodetree(self, add_as_independent_tree = False):
        """
        :param add_as_independent_tree: True if this should be a top-level data object,
                                        like a material or a whole Geo Nodes modifier,
                                        False if it should be created as a group node
                                        within the current open tree editor 
        """
        # this function can't handle material
        if (self.type == "MATERIAL") or (self.type == "ShaderNodeTree"):
            print("This function can't handle materials, try NS_mat_constructor")
        
        # Check for deprecated use of nodetree.type instead of .bl_idname
        if (self.type == "GEOMETRY"):
            self.type = "GeometryNodeTree"
        if (self.type == "COMPOSITING"):
            self.type = "CompositorNodeTree"
        if (self.type == "SHADER"):
            self.type = "ShaderNodeTree"
        if (self.type == "TEXTURE"):
            self.type = "TextureNodeTree"
        # Create a new node tree in blender and keep a reference to the data
        # b_ = blender
        self.b_nodeTree = bpy.data.node_groups.new(self.name, self.type)
        self.b_nodeTree_name_actual = self.b_nodeTree.name
        self.b_nodes = self.b_nodeTree.nodes

        if (add_as_independent_tree == True):
            # Try to get it to show up to the top level editor
            self.b_nodeTree.is_modifier = True
        else:
            # Add this tree as a group node to the current open node editor
            editor_node_tree = bpy.context.space_data.edit_tree
            # Get the right node type to create
            group_node_type = self.type.replace("Tree", "Group")
            # Create  the node in the current graph
            group_node = editor_node_tree.nodes.new( group_node_type)
            # Link it to our data
            group_node.node_tree = self.b_nodeTree

        self._created_nodes = []
        self._created_groups = {}

        # Construct groups first
        if self.groups is not None:
            print("Constructing groups")
            # NS_groups are only for nodetree info, not group and metadata info
            ns_grp : NS_group  
            for ns_grp in self.groups:
                print('Constructing group:' + ns_grp + '\n')
                b_group = bpy.data.node_groups.new(ns_grp, self.type)
                self._created_groups[ns_grp] = b_group.name
                # self._created_groups[grp] = group
            for b_grp in self._created_groups:
                try:
                    # self.construct(self.ns_groups[grp], group)
                    self.create_blender_nodes(self.groups[b_grp],
                                   self._created_groups[b_grp], is_nodegroup=True)  # causes crash when linking
                except Exception as e:
                    print('Constructing node group node tree failed')
                    print(e)
        else:
            print ("Didn't find groups to construct")

        # Now construct the node tree
        self.create_blender_nodes(self._nodes, self.b_nodeTree_name_actual, is_nodegroup = True)
        

    def create_blender_nodes(self, ns_nodes, nt_parent_name, is_nodegroup=False):
        """
        Constructs a node tree
        :param ns_nodes: node sharer dict
        :param nt_parent_name: name of node tree parent, either material or node group
        :param is_nodegroup: bool is node group
        
        """
        # b_nodes = nt.nodes  # original
        to_link = []
        to_parent = {}
        b_node_names = {}  # Node sharer name: blender actual name
        
        # Find the node tree that is open in the editor
        b_nodes = bpy.data.node_groups[nt_parent_name].nodes
        

        # Remove all the existing nodes in the current node tree,
        #  so that there's a blank sheet to add our new nodes to
        #  old comment: remove stock BSDF and output if creating a material
        if is_nodegroup is False:
            for node_to_remove in b_nodes:
                b_nodes.remove(node_to_remove)
                
        # Look at the nodes in ns_nodes, and make nodes in our blender node graph
        for key in ns_nodes:
            print('Constructing node:' + key + '\n')

            stored_ns_node = ns_nodes[key]

            bl_idname = stored_ns_node.get('bl_idname')
            name = stored_ns_node.get('name')

            # if is_material is True:
            # if True:
            created_blender_node = b_nodes.new(bl_idname)
            created_blender_node.name = name
            b_node_names[name] = created_blender_node.name
            # else:
            #     try:
            #         node = b_nodes[name]
            #     except Exception as e:
            #         print('No existing node with that name, creating...')
            #         print(e)
            #         node = b_nodes.new(bl_idname)
            #         node.name = name

            # self._created_nodes.append(node)

            loc = stored_ns_node.pop('location')
            created_blender_node.location = (loc[0], loc[1])

            ns_node_tree = stored_ns_node.pop('node_tree', None)
            if ns_node_tree is not None:
                try:
                    created_blender_node.node_tree = bpy.data.node_groups[self._created_groups[ns_node_tree]]
                except Exception as e:
                    print('Group node node tree assignment failed')
                    print(e)

            inputs = stored_ns_node.pop('inputs', None)
            if inputs is not None:
                for i in inputs:
                    v = inputs[i]
                    try:
                        created_blender_node.inputs[int(i)].default_value = v
                    except Exception as e:
                        print('Failed to set input default value')
                        print(e)

            out_dv = stored_ns_node.pop('out_dv', None)
            if out_dv is not None:
                for i in out_dv:
                    v = out_dv[i]
                    try:
                        created_blender_node.outputs[int(i)].default_value = v
                    except Exception as e:
                        print('Failed to set output default value')
                        print(e)

            outputs = stored_ns_node.pop('outputs', None)
            if outputs is not None:
                to_link.append({name: outputs})

            color_ramp = stored_ns_node.pop('color_ramp', None)
            if color_ramp is not None:
                elements = color_ramp['elements']
                created_blender_node.color_ramp.color_mode = color_ramp['color_mode']
                created_blender_node.color_ramp.hue_interpolation = color_ramp['hue_interpolation']
                created_blender_node.color_ramp.interpolation = color_ramp['interpolation']
                i = 0
                for p, c in elements.items():
                    if i > 1:
                        new_cr_ele = created_blender_node.color_ramp.elements.new(position=float(p))
                        new_cr_ele.color = c
                    else:
                        created_blender_node.color_ramp.elements[i].position = float(p)
                        created_blender_node.color_ramp.elements[i].color = c
                    i += 1

            mapping = stored_ns_node.pop('mapping', None)
            if mapping is not None:
                curves = mapping.pop('curves')
                for idc, curve in curves.items():
                    for idp, point in curve.items():
                        if int(idp) > 1:
                            created_blender_node.mapping.curves[int(idc)].points.new(point[0], point[1])
                        else:
                            created_blender_node.mapping.curves[int(idc)].points[int(idp)].location = point

                while len(mapping) > 0:
                    key, v = mapping.popitem()
                    try:
                        setattr(created_blender_node.mapping, key, v)
                    except Exception as e:
                        print('failed to set mapping attribute: ' + str(key))
                        print(e)

            parent = stored_ns_node.pop('parent', None)
            if parent is not None:
                to_parent[name] = parent

            while len(stored_ns_node) > 0:
                key, v = stored_ns_node.popitem()
                try:
                    # We can check for read only properties,
                    if (created_blender_node.is_property_readonly(key) == True):
                        print (" Property ' " + key + " ' was read only, didn't set")
                    else:
                        setattr(created_blender_node, key, v)
                except Exception as e:
                    print('failed to set attribute: ' + str(key))
                    print(e)
                    
        
        # Now link together our nodes in the blender node graph
        for l in to_link:
            key, v = l.popitem()

            for output, targets in v.items():
                for name, ids in targets.items():
                    input_ids = []
                    if isinstance(ids, int):  # ids can be int or list.
                        input_ids.append(ids)  # This is the very first backwards compatabilty compromise!
                    else:
                        input_ids.extend(ids)
                    for i in input_ids:
                        try:
                            # groups changed from using node.input / node.output to 
                            #  using nodegroup.interface
                            # nt.links.new(b_nodes[k].outputs[int(output)], b_nodes[name].inputs[i])  # original
                            bpy.data.node_groups[nt_parent_name].links.new(
                                bpy.data.node_groups[nt_parent_name].nodes[b_node_names[key]].outputs[int(output)],
                                bpy.data.node_groups[nt_parent_name].nodes[b_node_names[name]].inputs[i])  # test
                            

                        except Exception as e:
                            print('Failed to link')
                            print(e)
        
        # And set up our parent/child relationships of the nodes on the blender node graph
        for key, v in to_parent.items():
            try:
                bpy.data.node_groups[nt_parent_name].nodes[b_node_names[key]].parent = \
                    bpy.data.node_groups[nt_parent_name].nodes[b_node_names[v]]
                # Location of the frame, if shrink is active, depends on the location of the nodes parented to the frame
                # but the location of the nodes parented to the frame depends on the location of the frame
                # the end result is that the frame does not appear in correct position as when copied
                # tasking the location of a node and re-applying it after parenting to a frame does not solve the issue
            except Exception as e:
                print('Failed to parent node')
                print(e)


class NS_material(NS_nodetree):
    """Stores a material and its nodes"""
    """ Weird in that it stores data both as member variables
        but also as the member dictionary ns_mat"""
    def __init__(self, mat):
        super().__init__()
        self._mat = mat
        self.name = self._mat.name
        self.groups.clear()
        self.populate_nodetree(self._mat.node_tree)
        self.ns_mat = {'name': self.name,
                       'type': 'material',
                       'nodes': self._nodes}
        if self.groups != {}:
            self.ns_mat['groups'] = self.groups

    def dumps_mat_JSON(self):
        print('JSON dump of material')
        return self.dumps_JSON(self.ns_mat)

    def dump_mat_JSON(self):
        """Un indented JSON for compression"""
        return self.dump_JSON(self.ns_mat)

    def compress(self):
        prefix = self.prefix()
        try:
            # print('json string')
            json_str = self.dump_mat_JSON().encode("utf8")
            # print('compressed obj')
            compressed = zlib.compress(json_str, 9)
            encoded = base64.b64encode(compressed).decode()
            ns_string = prefix + encoded
            print('base64 encoded string(length = ' + str(len(ns_string)) + ') : \n')
            print(ns_string)
            print('\n')
            bpy.context.window_manager.clipboard = ns_string
            return ns_string, len(ns_string)
        except Exception as e:
            print("Failed in compress")
            print(e)

    def prefix(self):
        blender_version = bpy.app.version
        ns_version = str(0)
        prefix = 'NS' + ns_version + 'B' + str(blender_version[0]) + str(blender_version[1]) + str(
            blender_version[2]) + '!'
        return prefix


class NS_group(NS_nodetree):

    def __init__(self, nodetree):
        super().__init__()
        self._nt = nodetree
        self.properties = {}

        self.populate_nodetree()

    def populate_nodetree(self):
        for node in self._nt.nodes:
            self.add_node(node)

        self.properties = self.make_dict()

    def print_prop(self):
        pprint.pprint(self.properties)
        print('\n')

    def ret_nodes(self):
        d = self.make_dict()
        return d


class NS_mat_constructor(NS_nodetree):
    """NS_nodetree subclass, stores material meta and nodetree data,
        used when importing from JSON"""
    """ It works by uncompressing the JSON string,
        then it stores that into the dictionary ns_nodes.
    """

    def __init__(self, b64_string):
        """

        :param b64_string: node sharer compressed base 64 string
        """
        super().__init__()
        self.prefix = str(b64_string.split('!')[0])

        if str(self.prefix[:2]) != 'NS':
            return

        # uncompressed is a dictionary object, not a string
        self.uncompressed = self.uncompress(b64_string.split('!')[1])
        # ns_ = Node Sharer
        self.ns_nodes = self.uncompressed['nodes']

        CompFixer.fix(self.prefix, self.ns_nodes)  # Fix compatability


        self.ns_mat_name = self.uncompressed['name']
        self.ns_groups = self.uncompressed.pop('groups', None)

        # Create a new material in blender
        # b_ = blender
        self.b_mat = bpy.data.materials.new(name=self.ns_mat_name)
        self.b_mat_name_actual = self.b_mat.name
        self.b_mat.use_nodes = True
        self.b_nodes = self.b_mat.node_tree.nodes

        self._created_nodes = []
        self._created_groups = {}


        # Our data format:
        #  Metadata
        #  Main tree nodes
        #  dict of subtree nodetrees (:NS_group)
        #  
        # This way, a top level NS_material or NS_nodetree has
        #  all the info it needs to create nodes and link them all up
        #  We store all the subtrees as a dict so that we can connect
        #  them all, because Blender Group nodes only care about a link
        #  to a nodetree, so we can construct those without recursion (?)
        #   HOW DO WE DEAL WITH LINKS TO EXISTING NODES? I don't think we do
        # Construct groups first
        if self.ns_groups is not None:
            # NS_groups are only for nodetree info, not group and metadata info
            ns_grp : NS_group  
            for ns_grp in self.ns_groups:
                print('Constructing group:' + ns_grp + '\n')
                group = bpy.data.node_groups.new(ns_grp, 'ShaderNodeTree')
                self._created_groups[ns_grp] = group.name
                # self._created_groups[grp] = group
            for b_grp in self._created_groups:
                try:
                    # self.construct(self.ns_groups[grp], group)
                    self.constructNodes(self.ns_groups[b_grp],
                                   self._created_groups[b_grp], is_nodegroup=True)  # causes crash when linking
                except Exception as e:
                    print('Constructing node group node tree failed')
                    print(e)

        # Construct material node tree
        # self.construct(self.ns_nodes, self.b_mat.node_tree, is_material=True)  # Original

        self.constructNodes(self.ns_nodes, self.b_mat_name_actual,
                       is_material=True)

    def uncompress(self, s):
        """
        Uncompresses the base64 node sharer text string
        :param s: base64 encoded node sharer text string
        :return: the uncompressed material dict
        """
        try:
            print('uncompressing \n')
            compressed = base64.b64decode(s)
            json_str = zlib.decompress(compressed).decode('utf8')
            # print('JSON \n' + json_str + '\n')
            material = json.loads(json_str)
            print('pprint JSON \n')
            pprint.pprint(material)
            return material
        except Exception as e:
            print(e)

    def constructNodes(self, ns_nodes, nt_parent_name, is_material=False, is_nodegroup=False):
        """
        Constructs a node tree
        :param nt_parent_name: name of node tree parent, either material or node group
        :param is_nodegroup: bool is node group
        :param ns_nodes: node sharer dict
        :param is_material: bool is material
        """
        # b_nodes = nt.nodes  # original
        to_link = []
        to_parent = {}
        b_node_names = {}  # Node sharer name: blender actual name

        if is_material:
            b_nodes = bpy.data.materials[self.b_mat_name_actual].node_tree.nodes
        elif is_nodegroup:
            b_nodes = bpy.data.node_groups[nt_parent_name].nodes
        else:
            print('Did not specify material or node group')
            return

        # remove stock BSDF and output if creating a material
        if is_material is True:
            for node_to_remove in b_nodes:
                b_nodes.remove(node_to_remove)

        for key in ns_nodes:
            print('Constructing node:' + key + '\n')

            stored_ns_node = ns_nodes[key]

            bl_idname = stored_ns_node.pop('bl_idname')
            name = stored_ns_node.pop('name')

            # if is_material is True:
            # if True:
            created_blender_node = b_nodes.new(bl_idname)
            created_blender_node.name = name
            b_node_names[name] = created_blender_node.name
            # else:
            #     try:
            #         node = b_nodes[name]
            #     except Exception as e:
            #         print('No existing node with that name, creating...')
            #         print(e)
            #         node = b_nodes.new(bl_idname)
            #         node.name = name

            # self._created_nodes.append(node)

            loc = stored_ns_node.pop('location')
            created_blender_node.location = (loc[0], loc[1])

            ns_node_tree = stored_ns_node.pop('node_tree', None)
            if ns_node_tree is not None:
                try:
                    created_blender_node.node_tree = bpy.data.node_groups[self._created_groups[ns_node_tree]]
                except Exception as e:
                    print('Group node node tree assignment failed')
                    print(e)

            inputs = stored_ns_node.pop('inputs', None)
            if inputs is not None:
                for i in inputs:
                    v = inputs[i]
                    try:
                        created_blender_node.inputs[int(i)].default_value = v
                    except Exception as e:
                        print('Failed to set input default value')
                        print(e)

            out_dv = stored_ns_node.pop('out_dv', None)
            if out_dv is not None:
                for i in out_dv:
                    v = out_dv[i]
                    try:
                        created_blender_node.outputs[int(i)].default_value = v
                    except Exception as e:
                        print('Failed to set output default value')
                        print(e)

            outputs = stored_ns_node.pop('outputs', None)
            if outputs is not None:
                to_link.append({name: outputs})

            color_ramp = stored_ns_node.pop('color_ramp', None)
            if color_ramp is not None:
                elements = color_ramp['elements']
                created_blender_node.color_ramp.color_mode = color_ramp['color_mode']
                created_blender_node.color_ramp.hue_interpolation = color_ramp['hue_interpolation']
                created_blender_node.color_ramp.interpolation = color_ramp['interpolation']
                i = 0
                for p, c in elements.items():
                    if i > 1:
                        new_cr_ele = created_blender_node.color_ramp.elements.new(position=float(p))
                        new_cr_ele.color = c
                    else:
                        created_blender_node.color_ramp.elements[i].position = float(p)
                        created_blender_node.color_ramp.elements[i].color = c
                    i += 1

            mapping = stored_ns_node.pop('mapping', None)
            if mapping is not None:
                curves = mapping.pop('curves')
                for idc, curve in curves.items():
                    for idp, point in curve.items():
                        if int(idp) > 1:
                            created_blender_node.mapping.curves[int(idc)].points.new(point[0], point[1])
                        else:
                            created_blender_node.mapping.curves[int(idc)].points[int(idp)].location = point

                while len(mapping) > 0:
                    key, v = mapping.popitem()
                    try:
                        setattr(created_blender_node.mapping, key, v)
                    except Exception as e:
                        print('failed to set mapping attribute: ' + str(key))
                        print(e)

            parent = stored_ns_node.pop('parent', None)
            if parent is not None:
                to_parent[name] = parent

            while len(stored_ns_node) > 0:
                key, v = stored_ns_node.popitem()
                try:
                    setattr(created_blender_node, key, v)
                except Exception as e:
                    print('failed to set attribute: ' + str(key))
                    print(e)

        for l in to_link:
            key, v = l.popitem()

            for output, targets in v.items():
                for name, ids in targets.items():
                    input_ids = []
                    if isinstance(ids, int):  # ids can be int or list.
                        input_ids.append(ids)  # This is the very first backwards compatabilty compromise!
                    else:
                        input_ids.extend(ids)
                    for i in input_ids:
                        try:
                            # nt.links.new(b_nodes[k].outputs[int(output)], b_nodes[name].inputs[i])  # original
                            if is_material:
                                bpy.data.materials[self.b_mat_name_actual].node_tree.links.new(
                                    bpy.data.materials[self.b_mat_name_actual].node_tree.nodes[b_node_names[key]].outputs[
                                        int(output)],
                                    bpy.data.materials[self.b_mat_name_actual].node_tree.nodes[
                                        b_node_names[name]].inputs[i])  # test
                            elif is_nodegroup:
                                bpy.data.node_groups[nt_parent_name].links.new(
                                    bpy.data.node_groups[nt_parent_name].nodes[b_node_names[key]].outputs[int(output)],
                                    bpy.data.node_groups[nt_parent_name].nodes[b_node_names[name]].inputs[i])  # test
                        except Exception as e:
                            print('Failed to link')
                            print(e)

        for key, v in to_parent.items():
            try:
                if is_material:
                    bpy.data.materials[self.b_mat_name_actual].node_tree.nodes[b_node_names[key]].parent = \
                        bpy.data.materials[self.b_mat_name_actual].node_tree.nodes[b_node_names[v]]
                elif is_nodegroup:
                    bpy.data.node_groups[nt_parent_name].nodes[b_node_names[key]].parent = \
                        bpy.data.node_groups[nt_parent_name].nodes[b_node_names[v]]
                # Location of the frame, if shrink is active, depends on the location of the nodes parented to the frame
                # but the location of the nodes parented to the frame depends on the location of the frame
                # the end result is that the frame does not appear in correct position as when copied
                # tasking the location of a node and re-applying it after parenting to a frame does not solve the issue
            except Exception as e:
                print('Failed to parent node')
                print(e)


class OBJECT_MT_ns_copy_material(bpy.types.Operator):
    """Node Sharer: Copy complete material node setup as compressed string"""  # Use this as a tooltip for menu items and buttons.
    bl_idname = "node.ns_copy_material"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Copy material as a text string"  # Display name in the interface.
    bl_options = {'REGISTER'}  # 

    def execute(self, context):  # execute() is called when running the operator.
        
        my_mat = NS_material(context.material)
#        my_mat = NS_material(context.space_data.edit_tree)
        print("here is text2")
        my_mat.print_tree()
        ns_string, length = my_mat.compress()
        bpy.types.Scene.ns_string = ns_string
        text = 'Copied material as Node Sharer text string to clipboard. Text length: ' + str(length)
        self.report({'INFO'}, text)

        return {'FINISHED'}  # Lets Blender know the operator finished successfully.

class OBJECT_MT_ns_export_material(bpy.types.Operator):
    """Node Sharer: Export complete material node setup as a JSON text string to the clipboard"""  # Use this as a tooltip for menu items and buttons.
    bl_idname = "node.ns_export_material"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Export material as text string"  # Display name in the interface.
    bl_options = {'REGISTER'}  # 

    def execute(self, context):  # execute() is called when running the operator.
        
        # Materials have a bunch of properties outside of just the node tree,
        #  so if we're in the shader editor, we run the original code
        if (context.material): 
            print ("The current context has a material")
            my_mat = NS_material(context.material)
#        my_mat = NS_material(context.space_data.edit_tree) #DEBUG
        #my_mat.print_tree()
            json_string = my_mat.dumps_mat_JSON()
            print("jsonString type: {}".format(type(json_string)))
            bpy.context.window_manager.clipboard = json_string
        #text = 'yyyCopied material as Node Sharer text string to clipboard. Text length: '
        #self.report({'INFO'}, text)
        else:
            print("We were in a different node editor")
            editor_node_tree = context.space_data.edit_tree
            my_node_tree = NS_nodetree(editor_node_tree)
            for node in editor_node_tree.nodes:
                my_node_tree.add_node(node)
                print("Added node")
                
            json_string = my_node_tree.dumps_nodetree_JSON()
            bpy.context.window_manager.clipboard = json_string

        return {'FINISHED'}  # Lets Blender know the operator finished successfully.

class OBJECT_MT_ns_paste_material(bpy.types.Operator):
    """Node Sharer: Paste complete material node setup from text string"""  # Use this as a tooltip for menu items and buttons.
    bl_idname = "node.ns_paste_material"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Paste material from text string in clipboard"  # Display name in the interface.
    bl_options = {'REGISTER'}  #

    def execute(self, context):  # execute() is called when running the operator.
        print('Paste material')

        new_mat = NS_mat_constructor(bpy.context.window_manager.clipboard)
        try:
            text = 'Pasted material from Node Sharer text string. Material name: ' + str(new_mat.b_mat.name)
            level = 'INFO'
        except AttributeError:
            text = "Failed to paste material, make sure it\'s an actual Node Sharer text string"
            level = 'ERROR'
        self.report({level}, text)

        return {'FINISHED'}  # Lets Blender know the operator finished successfully.

class OBJECT_MT_ns_unregister_addon(bpy.types.Operator):
    """Node Sharer: unregisters the addon for debugging"""  # Use this as a tooltip for menu items and buttons.
    bl_idname = "node.ns_unregister_addon"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Unregister NodeSharer"  # Display name in the interface.
    bl_options = {'REGISTER'}  #

    def execute(self, context):  # execute() is called when running the operator.
        print('unregistering...')
        unregister()

        return {'FINISHED'}  # Lets Blender know the operator finished successfully.
    
class OBJECT_MT_ns_load_nodetree_from_file(bpy.types.Operator):
    """Node Sharer: Loads this node tree to a JSON file"""
    bl_idname = "node.ns_load_nodetree_from_file"
    bl_label = "Load Nodetree from File"
    bl_options = {'REGISTER'}
    
    # Function signature for the construct method
    #def construct(self, ns_nodes, nt, nt_parent_name, is_material=False, is_nodegroup=False):   
    """
        Constructs a node tree
        :param nt_parent_name: name of node tree parent, either material or node group
        :param is_nodegroup: bool is node group
        :param ns_nodes: node sharer dict
        :param nt: Blender node tree
        :param is_material: bool is material
        """
    def execute(self, context):  # execute() is called when running the operator.
        print('Paste tree')

        new_tree = NS_nodetree()
        new_tree.construct_from_JSON(bpy.context.window_manager.clipboard)
        try:
            text = 'Pasted material from Node Sharer text string. Tree name: ' + str(new_tree.b_nodeTree_name_actual)
            level = 'INFO'
        except AttributeError:
            text = "Failed to paste material, make sure it\'s an actual Node Sharer text string"
            level = 'ERROR'
        self.report({level}, text)

        return {'FINISHED'}  # Lets Blender know the operator finished successfully.

    # def execute(self, context):
    #     # Get our node tree
    #     editor_node_tree = context.space_data.edit_tree
    #     # make sure we have a node tree open in the editor
    #     if (editor_node_tree != None):
    #         my_node_tree = NS_nodetree(editor_node_tree.nodes)
#            my_node_tree.construct(my_node_tree._nodes,
#                        bpy.data.node_groups[0], #FIX THIS SO IT'S ACTUALLY THE NODETREE'S NAME
#                       is_material=False, is_nodegroup=True)
        
    
class OBJECT_MT_ns_save_nodetree_to_file(bpy.types.Operator):
    """Node Sharer: Saves this node tree to a JSON file"""
    bl_idname = "node.ns_save_nodetree_to_file"
    bl_label = "Save Nodetree to File"
    bl_options = {'REGISTER'}
    
    filename: StringProperty(
        name="Outdir Path",
        description="Where I will save my stuff",
        subtype='FILE_NAME'
        # subtype='DIR_PATH' is not needed to specify the selection mode.
        # But this will be anyway a directory path.
        ) # type: ignore
    
    
    filepath: StringProperty(
        name="Outdir Path",
        description="Where I will save my stuff",
        subtype='FILE_PATH'
        # subtype='DIR_PATH' is not needed to specify the selection mode.
        # But this will be anyway a directory path.
        )  # type: ignore
    @classmethod
    def poll(cls, context):
        return context.object is not None
    
    def execute(self, context):
        # guard against a switched context
        #if self.options.is_invoke:
            # The context may have changed since invoking the file selector.
        #        self.report({'ERROR'}, "Invalid context")
        #        return {'CANCELLED'}

        print("Selected file: '" + self.filename + "'")
        print("Full path: " + self.filepath)
        
        # Get our node tree
        editor_node_tree = context.space_data.edit_tree
        # make sure we have one
        if (editor_node_tree != None):
            my_node_tree = NS_nodetree(editor_node_tree.nodes)
            
            with open( self.filepath, "w") as file:
                file.write(my_node_tree.dumps_nodetree_JSON())
            print("finished")
        else:
            print("No node tree available, has the context changed?")

        return {'FINISHED'}

    def invoke(self, context, event):
        nodetree_name = context.space_data.edit_tree.name_full
        nodetree_name = nodetree_name.replace(" ", "")
        self.filename =  nodetree_name + ".json"
        # Open browser, take reference to 'self' read the path to selected
        # file, put path in predetermined self fields.
        # See: https://docs.blender.org/api/current/bpy.types.WindowManager.html#bpy.types.WindowManager.fileselect_add
        context.window_manager.fileselect_add(self)
        # Tells Blender to hang on for the slow user input
        return {'RUNNING_MODAL'}



def menu_func(self, context):
    self.layout.operator(OBJECT_MT_ns_copy_material.bl_idname)
    self.layout.operator(OBJECT_MT_ns_export_material.bl_idname)
    self.layout.operator(OBJECT_MT_ns_paste_material.bl_idname)
    self.layout.operator(OBJECT_MT_ns_save_nodetree_to_file.bl_idname)
    self.layout.operator(OBJECT_MT_ns_load_nodetree_from_file.bl_idname)
    self.layout.operator(OBJECT_MT_ns_unregister_addon.bl_idname)
    


def register():
    print("\n =============================================== \n")
    bpy.types.Scene.ns_string = bpy.props.StringProperty(name = "NodeString", default="")
    bpy.utils.register_class(OBJECT_MT_ns_copy_material)
    bpy.utils.register_class(OBJECT_MT_ns_export_material)
    bpy.utils.register_class(OBJECT_MT_ns_paste_material)
    bpy.utils.register_class(OBJECT_MT_ns_unregister_addon)
    bpy.utils.register_class(OBJECT_MT_ns_save_nodetree_to_file)
    bpy.utils.register_class(OBJECT_MT_ns_load_nodetree_from_file)
    bpy.types.NODE_MT_node.append(menu_func)
    print("registered Add-on: Node Sharer")
    print("\n =============================================== \n")


def unregister():
    bpy.utils.unregister_class(OBJECT_MT_ns_copy_material)
    bpy.utils.unregister_class(OBJECT_MT_ns_export_material)
    bpy.utils.unregister_class(OBJECT_MT_ns_paste_material)
    bpy.utils.unregister_class(OBJECT_MT_ns_unregister_addon)
    bpy.types.NODE_MT_node.remove(menu_func)
    print("unregistered Add-on: Node Sharer")


class CompFixer:
    """Version compatibility fixing code"""

    def __init__(self):
        pass

    @staticmethod
    def upgrade_to_blender2910(nodes):
        """
        Blender 2.91 adds a new input to the BSDF node, emit strength in slot 18, moving the previous slot 18 up etc.
        Anything that connect to slot 18 or above from before 2.91 will have its slot number increased by one.
        The input default values will also be updated to match
        :param nodes: node tree as dict, nodes or groups
        """
        _BSDF_node_names = []
        print('Upgrading nodes to Blender 2.91...')
        for n in nodes:
            node = nodes[n]

            if node['bl_idname'] == 'ShaderNodeBsdfPrincipled':
                # Save the node name for so connections can be updated
                _BSDF_node_names.append(node['name'])

                # Shift the input default values slots up
                for i in reversed(range(18, 22 + 1)):
                    nodes[n]['inputs'][str(i)] = node['inputs'][str(i - 1)]
                del nodes[n]['inputs']['18']

        for n in nodes:
            node = nodes[n]
            try:
                for output, targets in node['outputs'].items():
                    for name, ids in targets.items():
                        if name in _BSDF_node_names:
                            # increment if the slot is 18 or higher
                            if isinstance(ids, int) and ids >= 18:
                                nodes[n]['outputs'][output][name] = ids + 1
                            elif isinstance(ids, list):
                                tmp_ids = ids.copy()
                                for pos, i in enumerate(ids):
                                    if i >= 18:
                                        tmp_ids[pos] = i + 1
                                nodes[n]['outputs'][output][name] = tmp_ids

            except KeyError:
                print('No outputs in node: {}'.format(node['name']))

        print('Nodes upgraded to comply with Blender 2.91')

    @staticmethod
    def downgrade_from_blender2910(nodes):
        """
        Blender 2.91 adds a new input to the BSDF node, emit strength in slot 18, moving the previous slot 18 up etc.
        Anything that connect to slot 18 or above from 2.91 or after will have its slot number decreased by one.
        The input default values will also be updated to match
        :param nodes: node tree as dict, nodes or groups
        """
        _BSDF_node_names = []
        print('Downgrading nodes from Blender 2.91...')
        for n in nodes:
            node = nodes[n]

            if node['bl_idname'] == 'ShaderNodeBsdfPrincipled':
                # Save the node name for so connections can be updated
                _BSDF_node_names.append(node['name'])

                # Shift the input default values slots down
                for i in range(18, 22):
                    nodes[n]['inputs'][str(i)] = node['inputs'][str(i + 1)]
                del nodes[n]['inputs']['22']

        for n in nodes:
            node = nodes[n]
            try:
                for output, targets in node['outputs'].items():
                    for name, ids in targets.items():
                        if name in _BSDF_node_names:
                            # decrement if the slot is 19 or higher
                            if isinstance(ids, int) and ids >= 19:
                                nodes[n]['outputs'][output][name] = ids - 1
                            elif isinstance(ids, list):
                                tmp_ids = ids.copy()
                                for pos, i in enumerate(ids):
                                    if i >= 19:
                                        tmp_ids[pos] = i - 1
                                nodes[n]['outputs'][output][name] = tmp_ids

            except KeyError:
                print('No outputs in node: {}'.format(node['name']))

        print('Nodes downgraded to comply with pre Blender 2.91')

    @staticmethod
    def upgrade_to_blender3000(nodes):
        """
        Blender 3.0 adds two new(undocumented) inputs to the BSDF node, Subsurface IOR and Subsurface Anisotropy in slots 4 & 5, moving the previous slot 4,5 up etc.
        Anything that connects to slot 4 or above from before 3.0 will have its slot number increased by two.
        The input default values will also be updated to match
        :param nodes: node tree as dict, nodes or groups
        """
        _BSDF_node_names = []
        print('Upgrading nodes to Blender 3.0...')
        for n in nodes:
            node = nodes[n]

            if node['bl_idname'] == 'ShaderNodeBsdfPrincipled':
                # Save the node name for so connections can be updated
                _BSDF_node_names.append(node['name'])

                # Shift the input default values slots up
                for i in reversed(range(4, 24 + 1)):
                    try:
                        nodes[n]['inputs'][str(i)] = node['inputs'][str(i - 2)]
                    except KeyError:
                        """Cant move slots that don't exist, for example slot 18 if the material was previously 
                        upgraded to blender 2.91 """
                        pass
                del nodes[n]['inputs']['4']

        for n in nodes:
            node = nodes[n]
            try:
                for output, targets in node['outputs'].items():
                    for name, ids in targets.items():
                        if name in _BSDF_node_names:
                            # increment by 2 if the slot is 4 or higher
                            if isinstance(ids, int) and ids >= 4:
                                nodes[n]['outputs'][output][name] = ids + 2
                            elif isinstance(ids, list):
                                tmp_ids = ids.copy()
                                for pos, i in enumerate(ids):
                                    if i >= 4:
                                        tmp_ids[pos] = i + 2
                                nodes[n]['outputs'][output][name] = tmp_ids

            except KeyError:
                print('No outputs in node: {}'.format(node['name']))

        print('Nodes upgraded to comply with Blender 3.0')

    @staticmethod
    def version_difference(prefix):
        """
        Not used atm
        :param prefix:
        :return:
        """
        bv = bpy.app.version
        blender_version = int(str(bv[0]) + str(bv[1]) + str(bv[2]))

        ns_bv = int(prefix.split('B')[1])
        if ns_bv != blender_version:
            return True
        else:
            return False

    @staticmethod
    def fix(prefix, nodes):
        """
        Fix compatibility
        :param prefix: Node Sharer prefix
        :param nodes: Node Sharer node dict
        """
        bv = bpy.app.version

        if bv >= (2, 91, 0):
            if 2800 < int(prefix.split('B')[1]) < 2910:
                CompFixer.upgrade_to_blender2910(nodes)
        if bv >= (3, 0, 0):
            if 2800 < int(prefix.split('B')[1]) < 3000:
                CompFixer.upgrade_to_blender3000(nodes)
        elif bv < (2, 91, 0):
            if int(prefix.split('B')[1]) >= 2910:
                CompFixer.downgrade_from_blender2910(nodes)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()
