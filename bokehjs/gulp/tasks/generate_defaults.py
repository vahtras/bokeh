from bokeh.plot_object import PlotObject
import bokeh.models as models
import inspect
from bokeh._json_encoder import serialize_json
from json import loads
import codecs
import sys
import os

dest_dir = sys.argv[1]

classes = [member for name, member in inspect.getmembers(models) if inspect.isclass(member)]

plot_object_class = next(klass for klass in classes if klass.__name__ == 'PlotObject')
widget_class = next(klass for klass in classes if klass.__name__ == 'Widget')

# getclasstree returns a list which contains [ (class, parentClass), [(subClassOfClass, class), ...]]
# where the subclass list is omitted if there are no subclasses.
# If you say unique=True then mixins will be registered as leaves so don't use unique=True,
# and expect to have duplicates in the result of leaves()
all_tree = inspect.getclasstree(classes, unique=False)

def leaves(tree, underneath):
    if len(tree) == 0:
        return []
    elif len(tree) > 1 and isinstance(tree[1], list):
        subs = tree[1]
        if underneath is None or tree[0][0] != underneath:
            return leaves(subs, underneath) + leaves(tree[2:], underneath)
        else:
            # underneath=None to return all leaves from here out
            return leaves(subs, underneath=None)
    else:
        leaf = tree[0]
        tail = tree[1:]
        if leaf[0] == underneath:
            return [leaf]
        elif underneath is not None:
            return leaves(tail, underneath)
        else:
            return [leaf] + leaves(tail, underneath)

all_json = {}
for leaf in leaves(all_tree, plot_object_class):
    klass = leaf[0]
    vm_name = klass.__view_model__
    if vm_name in all_json:
        continue
    defaults = {}
    for name in klass.class_properties():
        prop = getattr(klass, name)
        default = prop.default
        if isinstance(default, PlotObject):
            ref = default.ref
            raw_attrs = default.vm_serialize(changed_only=False)
            del raw_attrs['id']
            for (k, v) in raw_attrs.items():
                # we can't serialize Infinity ... this hack is also in PlotObject.
                if isinstance(v, float) and v == float('inf'):
                    raw_attrs[k] = None
            attrs = loads(serialize_json(raw_attrs, sort_keys=True))
            del ref['id']
            ref['attributes'] = attrs
            default = ref
        elif isinstance(default, float) and default == float('inf'):
            default = None
        defaults[name] = default
    all_json[vm_name] = defaults

widgets_json = {}
for leaf_widget in leaves(all_tree, widget_class):
    klass = leaf_widget[0]
    vm_name = klass.__view_model__
    if vm_name not in widgets_json:
        widgets_json[vm_name] = all_json[vm_name]
        del all_json[vm_name]

def output_defaults_module(filename, defaults):
    output = serialize_json(defaults, sort_keys=True, indent=4, separators=[',', ':'])
    coffee_template = \
    """
all_defaults = %s;

get_defaults = (name) ->
  if name of all_defaults
    all_defaults[name]
  else
    null

all_view_model_names = () ->
  Object.keys(all_defaults)

module.exports = {
  get_defaults: get_defaults
  all_view_model_names: all_view_model_names
}
"""
    try:
        os.makedirs(os.path.dirname(filename))
    except OSError as e:
        pass
    f = codecs.open(filename, 'w', 'utf-8')
    f.write(coffee_template % output)
    f.close()

    print("Wrote %s with %d model classes" % (filename, len(defaults)))


output_defaults_module(filename = os.path.join(dest_dir, 'common/defaults.coffee'),
                       defaults = all_json)
output_defaults_module(filename = os.path.join(dest_dir, 'widget/defaults.coffee'),
                       defaults = widgets_json)



