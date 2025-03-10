from __future__ import print_function

import codecs
import getopt
import glob
import os
import re
import shutil
import sys
try:
    # Python 2.5
    from xml.etree import ElementTree

except ImportError:
    from elementtree import ElementTree


cmdline_templates = {}


def escapeString(string):
    return re.sub(r"([=*\(\)|\-!@~\"&/\\\^\$\=])", r"\\\1", string)


def tagname(element):
    # pylint: disable=W0621
    names = element.tag.split("}")
    if len(names) == 0:
        return ""
    return names.pop()


def escape(txt):
    # return txt.replace("*", "\\*")
    return escapeString(txt)


def xml_desc_lines(n):
    # pylint: disable=W0621
    desc_node = n.find('description')
    if desc_node is not None and desc_node.text is not None:
        return [l.strip() for l in desc_node.text.strip().replace("\r", "").split('\n')]
    return []


def xml_collect_params(param_nodes, struct_nodes, group_nodes, prefix):
    # pylint: disable=W0621
    if param_nodes is None and group_nodes is None:
        return ""
    options = ""

    for param_node in param_nodes:
        name = param_node.get('name')
        type_ = param_node.get('type')
        unit = param_node.get('unit')

        # If name is not defined, remove the trailing dot and set name
        # to an empty string
        if name is None:
            prefix = prefix[:-1]
            name = ""

        desc = xml_desc_lines(param_node)
        options += "\n.. confval:: %s%s\n\n" % (prefix, name)
        default = param_node.get('default')

        if default:
            options += "   Default: ``%s``\n\n" % default
        if type_:
            options += "   Type: *%s*\n\n" % type_
        if unit:
            options += "   Unit: *%s*\n\n" % unit
        # Description available
        if len(desc) > 0:
            for line in desc:
                options += "   %s\n" % escape(line)
        # Nothing
        else:
            options += "   *No description available*"
        options += "\n"

    for struct_node in struct_nodes:
        struct_prefix = prefix + '$name.' # pylint: disable=W1401
        options += "\n"
        options += ".. note::\n\n"
        options += "   **%s\***\n" % struct_prefix # pylint: disable=W1401

        desc = xml_desc_lines(struct_node)
        if len(desc) > 0:
            for l in desc:
                options += "   *" + l + "*\n"

        options += "   $name is a placeholder for the name to be used" # pylint: disable=W1401
        link = struct_node.get('link')
        if link:
            options += " and needs to be added to :confval:`%s` to become active.\n\n" % link
            options += "   .. code-block:: sh\n\n"
            options += "      %s = a,b\n" % link
            if struct_has_named_parameters(struct_node):
                options += "      %sa.value1 = ...\n" % prefix
                options += "      %sb.value1 = ...\n" % prefix
                options += "      # c is not active because it has not been added\n"
                options += "      # to the list of %s\n" % link
                options += "      %sc.value1 = ...\n" % prefix
            else:
                options += "      %sa = ...\n" % prefix
                options += "      %sb = ...\n" % prefix
                options += "      # c is not active because it has not been added\n"
                options += "      # to the list of %s\n" % link
                options += "      %sc = ...\n" % prefix
        else:
            options += ".\n"
        options += "\n"

        options += xml_collect_params(
            struct_node.findall('parameter'),
            struct_node.findall('struct'),
            struct_node.findall('group'),
            struct_prefix)

    for group_node in group_nodes:
        group_prefix = prefix + group_node.get('name') + '.'
        desc = xml_desc_lines(group_node)
        if len(desc) > 0:
            options += "\n"
            options += ".. note::\n"
            options += "   **%s\***\n" % group_prefix # pylint: disable=W1401
            for l in desc:
                options += "   *" + l + "*\n"
            options += "\n\n"

        options += xml_collect_params(
            group_node.findall('parameter'),
            group_node.findall('struct'),
            group_node.findall('group'),
            group_prefix)

    return options


def xml_collect_options(mod_node, prefix=""):
    # pylint: disable=W0621
    cfg_node = mod_node.find('configuration')
    if cfg_node is None:
        return ""

    param_nodes = cfg_node.findall('parameter')
    struct_nodes = cfg_node.findall('struct')
    group_nodes = cfg_node.findall('group')

    options = xml_collect_params(
        param_nodes, struct_nodes, group_nodes, prefix)
    return options


def xml_collect_cmdline(mod_node, publicids_only):
    # pylint: disable=W0621
    cmd_node = mod_node.find("command-line")
    if cmd_node is None:
        return ""

    group_nodes = cmd_node.findall("group")
    synopsis = cmd_node.find("synopsis")
    desc = xml_desc_lines(cmd_node)

    if len(group_nodes) == 0 and synopsis is None and len(desc) == 0:
        return ""

    options = '''

Command-Line Options
====================

.. program:: %s

''' % mod_node.get('name')

    if synopsis is not None:
        for line in [s.strip() for s in synopsis.text.strip().split("\n")]:
            if not line:
                continue
            options += ":program:`%s`\n\n" % line.strip()

    if len(desc) > 0:
        for line in desc:
            options += "%s\n" % escape(line)
        options += "\n"

    for group_node in group_nodes:
        name = group_node.get('name')
        if name:
            options += '''
%s
%s

''' % (name, '-'*len(name))

        if not publicids_only:
            optionref_nodes = group_node.findall('optionReference')
            for optionref_node in optionref_nodes:
                try:
                    publicID = optionref_node.text.strip()
                except BaseException:
                    print("WARNING: publicID is empty", file=sys.stderr)
                    continue
                if publicID not in cmdline_templates:
                    print("WARNING: option with publicID '{}' is not " \
                          "available".format(publicID), file=sys.stderr)
                    continue
                options += cmdline_templates[publicID]

        option_nodes = group_node.findall('option')
        for option_node in option_nodes:
            flag = option_node.get('flag')
            long_flag = option_node.get('long-flag')
            param_ref = option_node.get('param-ref')
            flags = ""
            if flag:
                flags += "-" + flag
            if long_flag:
                if flags:
                    flags += ", "
                flags += "--" + long_flag

            arg = option_node.get('argument')
            if arg:
                arg = " " + arg
            else:
                arg = ""

            option = ".. option:: %s%s\n\n" % (flags, arg)

            if param_ref:
                option += "   Overrides configuration parameter :confval:`%s`.\n" % param_ref
            desc = xml_desc_lines(option_node)
            if len(desc) > 0:
                for line in desc:
                    option += "   %s\n" % escape(line)
            option += "\n"

            publicID = option_node.get('publicID')
            if publicID:
                cmdline_templates[publicID] = option

            if not publicids_only:
                options += option

    return options


def find_doc_dirs(directory):
    # pylint: disable=W0621
    visited = set()
    # The followlinks option has been added with Python 2.6
    if sys.version_info >= (2, 6):
        for root, _, _ in os.walk(directory, followlinks=True):
            if os.path.basename(root) == "descriptions":
                abs_root = os.path.abspath(os.path.realpath(root))
                if not abs_root in visited:
                    visited.add(abs_root)
                    yield abs_root
    else:
        for root, _, _ in os.walk(directory):
            if os.path.basename(root) == "descriptions":
                abs_root = os.path.abspath(os.path.realpath(root))
                if not abs_root in visited:
                    visited.add(abs_root)
                    yield abs_root


def get_app_rst(searchpaths, appname):
    # pylint: disable=W0621
    for path in searchpaths:
        if os.path.exists(os.path.join(path, appname + ".rst")):
            return os.path.join(path, appname + ".rst")

    return ""


def get_app_binding_rst(searchpaths, appname):
    # pylint: disable=W0621
    for path in searchpaths:
        if os.path.exists(os.path.join(path, appname + "_binding.rst")):
            return os.path.join(path, appname + "_binding.rst")

    return ""


# Copies the contents of src to dst.
def copy_dir(src, dst):
    # pylint: disable=W0621
    for f in glob.glob(os.path.join(src, "*")):
        if os.path.isdir(f):
            shutil.copytree(f, os.path.join(dst, os.path.basename(f)))
        else:
            shutil.copyfile(f, os.path.join(dst, os.path.basename(f)))


def struct_has_named_parameters(node):
    # pylint: disable=W0621
    param_nodes = node.findall('parameter')
    struct_nodes = node.findall('struct')
    group_nodes = node.findall('group')

    if len(struct_nodes) > 0:
        return True
    if len(group_nodes) > 0:
        return True

    # Two unnamed parameter nodes are not allowed, so one must
    # have a name
    if len(param_nodes) > 1:
        return True

    if len(param_nodes) == 0:
        return False
    if param_nodes[0].get('name'):
        return True

    return False

def print_usage(appname, output):
    print("""usage: {} [options] <build dir>

options:
    -h [ --help ]       print this help message
       [ --all ]        include documentation of contributions
       [ --html ]       generate HTML pages
       [ --man ]        generate MAN pages
       [ --pdf ]        generate PDF manual
""".format(appname), file=output)


# MAIN goes here ...
base_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
print("Building configuration from '{}'".format(base_dir), file=sys.stderr)

out_build_dir = "build-doc"


try:
    opts, args = getopt.getopt(
        sys.argv[1:], 'h', ['help', 'all', 'html', 'man', 'pdf'])
except getopt.GetoptError as e:
    print("error: {}\n".format(e), file=sys.stderr)
    print_usage(sys.argv[0], sys.stderr)
    sys.exit(1)

# By default the contrib directory is ignored when building the
# documentation. If contrib directories should be included in the
# build then pass "--all".
allowContrib = False
build_html = False
build_man = False
build_pdf = False

for o, arg in opts:
    if o in ('-h', '--help'):
        print_usage(sys.argv[0], sys.stdout)
        sys.exit(0)
    if o == '--html':
        build_html = True
    if o == '--man':
        build_man = True
    if o == '--pdf':
        build_pdf = True
    if o == '--all':
        allowContrib = True

if not args:
    print("error: build directory not specified\n", file=sys.stderr)
    print_usage(sys.argv[0], sys.stderr)
    sys.exit(1)
elif len(args) > 1:
    print("error: to many remaining parameters\n", file=sys.stderr)
    print_usage(sys.argv[0], sys.stderr)
    sys.exit(1)
elif not any([build_html, build_man, build_pdf]):
    print("error: no build target specified\n", file=sys.stderr)
    print_usage(sys.argv[0], sys.stderr)
    sys.exit(1)

out_build_dir = args[0]

print("""Build params
    output build dir    : {}
    include contrib dirs: {}
    build HTML          : {}
    build MAN           : {}
    build PDF           : {}""".format(
        out_build_dir, allowContrib, build_html, build_man, build_pdf),
      file=sys.stderr)

# Collect doc directories from source tree
source_dir = os.path.abspath(os.path.join(base_dir, "..", "src", "base"))
doc_dirs = list(find_doc_dirs(source_dir))
print("Using source code repo from '{}' (#doc dirs: {})".format(
    source_dir, doc_dirs), file=sys.stderr)

if allowContrib:
    source_dir = os.path.abspath(os.path.join(base_dir, "..", "src", "extras"))
    contrib_dirs = list(find_doc_dirs(source_dir))
    doc_dirs += contrib_dirs
    print("Using source code repo from '{}' (#doc dirs: {})".format(
        source_dir, contrib_dirs), file=sys.stderr)

toc_tmp_dir = "toc"

out_dir = os.path.join(out_build_dir, "src")
out_struct_dir = os.path.join(out_dir, toc_tmp_dir)

if os.path.exists(out_dir):
    print("Cleaning target dir")
    shutil.rmtree(out_dir)


if not os.path.exists(out_struct_dir):
    try:
        os.makedirs(out_struct_dir)
    except Exception as e:
        print("ERROR: creating build directory '{}' failed: {}".format(
            out_struct_dir, e), file=sys.stderr)
        sys.exit(1)


categories = {}
app_nodes = []
app_plugin_nodes = {}
app_binding_nodes = {}
global_node = None

# Read all xml files in all doc dirs and grab the "module" node
# Plugins and bindings will follow later
for doc_dir in doc_dirs:
    for f in glob.glob(os.path.join(doc_dir, "*.xml")):
        try:
            xmlTree = ElementTree.parse(f)
        except Exception as e:
            print("ERROR: {}: parsing failed: {}".format(f, e), file=sys.stderr)
            sys.exit(1)

        root = xmlTree.getroot()
        if root is None:
            print("ERROR: {}: no root tag defined".format(f), file=sys.stderr)
            sys.exit(1)

        if tagname(root) != "seiscomp":
            print("ERROR: {}: invalid root tag: expected 'seiscomp'".format(f),
                  file=sys.stderr)
            sys.exit(1)

        for node in root:
            tag = tagname(node)
            if tag == "module":
                name = node.get('name')
                if not name:
                    print("ERROR: {}: module name not defined".format(f),
                          file=sys.stderr)
                    sys.exit(1)

                # The global configuration will be handled differently
                if name == "global":
                    global_node = node
                    continue

                category = node.get('category')
                if not category:
                    category = "Modules"

                toks = category.split('/')
                ct = []
                for t in toks[:-1]:
                    ct = ct + [t]
                    if '/'.join(ct) not in categories:
                        categories['/'.join(ct)] = []

                # Add node to category map
                try:
                    categories[category].append(node)
                except BaseException:
                    categories[category] = [node]

                app_nodes.append(node)

            elif tag == "plugin":
                name = node.get('name')
                if not name:
                    print("ERROR: {}: plugin name not defined".format(f),
                          file=sys.stderr)
                    sys.exit(1)

                try:
                    extends = node.find('extends').text.strip()
                except BaseException:
                    print("ERROR: {}: plugin extends not defined".format(f),
                          file=sys.stderr)
                    sys.exit(1)

                # Save all plugins of a module
                try:
                    app_plugin_nodes[extends].append(node)
                except BaseException:
                    app_plugin_nodes[extends] = [node]

            elif tag == "binding":
                modname = node.get('module')
                if not modname:
                    print("ERROR: {}: binding module not defined".format(f),
                          file=sys.stderr)
                    sys.exit(1)

                if node.get('category') and not node.get('name'):
                    print("ERROR: {}: binding category defined but no name " \
                          "given".format(f), file=sys.stderr)
                    sys.exit(1)

                # Save all plugins of a module
                try:
                    app_binding_nodes[modname].append(node)
                except BaseException:
                    app_binding_nodes[modname] = [node]


# categories hold pair [category, node]
# app_refs holds [reference_link, [section name, nodes]]
app_refs = {}
placeholder_gui_refs = ""

for key, value in sorted(categories.items()):
    dirs = key.split('/')
    section = dirs[-1]
    section_path = dirs[:-1]

    if len(section_path) > 0:
        link = os.path.join(toc_tmp_dir, *section_path).lower()
        path = os.path.join(out_dir, link)
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except Exception as e:
                print("ERROR: creating path '{}' failed: {}".format(path, e),
                      file=sys.stderr)
                sys.exit(1)
        link = os.path.join(link, section.lower())
    else:
        link = os.path.join(toc_tmp_dir, section.lower())

    app_refs[link] = [section_path, section, value]


placeholder_app_refs = ""
placeholder_plugins_refs = "   /%s/extensions" % toc_tmp_dir
refs = {}
plugin_refs = {}

app_path = os.path.join(out_dir, "apps")
if not os.path.exists(app_path):
    try:
        os.makedirs(app_path)
    except Exception as e:
        print("ERROR: creating path '{}' failed: {}".format(app_path, e),
              file=sys.stderr)
        sys.exit(1)


print("Generating document structure")

# Generate plugin structure
f = open(os.path.join(out_dir, toc_tmp_dir, "extensions.rst"), "w")
f.write('''\
##########
Extensions
##########

.. toctree::
   :maxdepth: 2

''')


out_struct_plugin_dir = os.path.join(out_struct_dir, "extensions")
if not os.path.exists(out_struct_plugin_dir):
    try:
        os.makedirs(out_struct_plugin_dir)
    except BaseException as e:
        print("ERROR: creating build directory '{}' failed: {}".format(
            out_struct_plugin_dir, e), file=sys.stderr)
        sys.exit(1)

# Save the global reference for each plugin
plugins_with_ref = {}

for app in sorted(app_plugin_nodes.keys()):
    plugins = app_plugin_nodes.get(app)
    plugin_files = []
    for p in plugins:
        desc_name = (app + "_" + p.get('name')).lower()
        desc_file = get_app_rst(doc_dirs, desc_name)
        if not desc_file:
            continue
        doc = codecs.open(desc_file, "r", "utf-8").read()
        plugin_file = os.path.join(app_path, desc_name + ".rst")
        plugin_files.append(desc_name)

        plugin_refs[p] = desc_name

        plugins_with_ref[p] = desc_name
        pf = codecs.open(plugin_file, "w", "utf-8")

        pf.write(".. _%s:\n\n" % desc_name)
        pf.write(("#" * len(p.get('name'))) + "\n")
        pf.write(p.get('name') + "\n")
        pf.write(("#" * len(p.get('name'))) + "\n\n")

        desc = "\n".join(xml_desc_lines(p))
        if not desc:
            desc = p.get('name')

        pf.write(desc + "\n\nDescription\n===========\n\n")

        pf.write(doc)

        options = xml_collect_options(p)
        if options:
            pf.write('''
.. _%s_configuration:

Module Configuration
====================

%s
''' % (desc_name, options))

        pf.close()

    if len(plugin_files) == 0:
        continue

    f.write("   /%s/extensions/%s\n" % (toc_tmp_dir, app))

    pf = open(os.path.join(out_struct_plugin_dir, "%s.rst" % app.lower()), "w")
    pf.write("%s\n" % ("#" * len(app)))
    pf.write("%s\n" % app)
    pf.write("%s\n\n" % ("#" * len(app)))

    pf.write(".. toctree::\n")
    pf.write("   :maxdepth: 2\n\n")

    for fn in plugin_files:
        pf.write("   /apps/%s\n" % fn)
    pf.close()

f.close()


# Generate app structure
for ref, nodes in sorted(app_refs.items()):
    section_path = nodes[0]
    section = nodes[1]
    xml_nodes = nodes[2]

    if section.lower() == "gui":
        for n in sorted(xml_nodes, key=lambda n: n.get('name')):
            placeholder_gui_refs += "   /apps/" + n.get('name').lower() + "\n"
        continue
    if len(section_path) == 1 and section_path[0].lower() == "gui":
        placeholder_gui_refs += "   /" + ref + "\n"
    elif len(section_path) == 0:
        placeholder_app_refs += "   /" + ref + "\n"

    try:
        f = open(os.path.join(out_dir, ref) + ".rst", "w")
    except BaseException:
        print("ERROR: unable to create index file: {}".format(ref),
              file=sys.stderr)
        sys.exit(1)

    # Create section files
    f.write('#'*len(section) + "\n")
    f.write("%s\n" % section)
    f.write('#'*len(section) + "\n")
    f.write("\n")
    f.write(".. toctree::\n")
    f.write("   :maxdepth: 1\n")
    f.write("\n")

    for n in sorted(xml_nodes, key=lambda n: n.get('name')):
        f.write("   /apps/" + n.get('name').lower() + "\n")

    my_path = section_path + [section]
    child_refs = []
    for ref2, nodes2 in list(app_refs.items()):
        if nodes2[0] == my_path:
            child_refs.append(ref2)

    for cref in sorted(child_refs):
        f.write("   /" + cref + "\n")

    f.close()

# Prepend global
if global_node is not None:
    placeholder_app_refs = "   /apps/global\n" + placeholder_app_refs

# Copy conf.py template
print("Copy conf.py template")

release = ""
version_major = 0
version_minor = 0
version_patch = 0

f = open(os.path.join(base_dir, "..", "src",
                      "system", "libs", "seiscomp", "version.h"))
for l in f.readlines():
    l = l.strip()
    if l.startswith('#define SEISCOMP_RELEASE_BRANCH'):
        release = l[31:].strip()
    elif l.startswith('#define SEISCOMP_VERSION_MAJOR'):
        version_major = l[30:].strip()
    elif l.startswith('#define SEISCOMP_VERSION_MINOR'):
        version_minor = l[30:].strip()
    elif l.startswith('#define SEISCOMP_VERSION_PATCH'):
        version_patch = l[30:].strip()
f.close()

f = open(os.path.join(base_dir, "templates", "conf.py"), "r")
c = f.read().replace("${version}", "\"%s.%s.%s\"" % (
    version_major, version_minor, version_patch)).replace("${release}", "%s" % release)
f.close()
f = open(os.path.join(out_dir, "conf.py"), "w")
f.write(c)
f.close()
#shutil.copyfile(os.path.join(base_dir, "templates", "conf.py"), os.path.join(out_dir, "conf.py"))

# Copy base directory
print("Copy base directory")
out_base_dir = os.path.join(out_dir, "base")
shutil.copytree(os.path.join(base_dir, "base"), out_base_dir)

# Copy media files
for doc_dir in doc_dirs:
    if os.path.exists(os.path.join(doc_dir, "media")):
        print("Copy media files from %s" % os.path.join(doc_dir, "media"))
        out_media_dir = os.path.join(out_dir, "apps", "media")
        if not os.path.exists(out_media_dir):
            try:
                os.makedirs(out_media_dir)
            except BaseException:
                pass
        copy_dir(os.path.join(doc_dir, "media"), out_media_dir)


# Create index.rst
print("Generate index.rst")
t = open(os.path.join(base_dir, "templates", "index.rst")).read()
open(os.path.join(out_dir, "index.rst"), "w").write(t.replace(
    "${generator.refs.apps}", placeholder_app_refs).replace(
        "${generator.refs.extensions}", placeholder_plugins_refs))

print("Generate modules.rst")
t = open(os.path.join(base_dir, "templates", "modules.rst")).read()
open(os.path.join(out_dir, "modules.rst"), "w").write(t.replace(
    "${generator.refs.apps}", placeholder_app_refs).replace(
        "${generator.refs.extensions}", placeholder_plugins_refs))

print("Generate gui.rst")
t = open(os.path.join(base_dir, "templates", "gui.rst")).read()
open(os.path.join(out_dir, "gui.rst"), "w").write(
    t.replace("${generator.refs.gui}", placeholder_gui_refs))

# Create application .rst files
print("Generating app .rst files")

if not global_node is None:
    node_list = app_nodes + [global_node]
else:
    node_list = app_nodes

# First pass, collect commandline templates for options with a publicID
for n in node_list:
    xml_collect_cmdline(n, True)

man_pages = []

for n in node_list:
    app_name = n.get('name')
    filename = os.path.join(app_path, (app_name + ".rst").lower())
    man_pages.append((app_name.lower(), n.get('author')))
    try:
        f = codecs.open(filename, "w", "utf-8")
    except Exception as e:
        print("ERROR: unable to create app rst '{}': {}".format(filename, e),
              file=sys.stderr)
        sys.exit(1)

    desc = "\n".join(xml_desc_lines(n))
    if not desc:
        desc = app_name

    app_rst = get_app_rst(doc_dirs, app_name)
    if app_rst:
        doc = codecs.open(app_rst, "r", "utf-8").read()
        # Copy original .rst to .doc
        #shutil.copyfile(os.path.join(base_dir, "apps", app_name + ".rst"),
        #                os.path.join(out_dir, "apps", app_name + ".doc"))
    else:
        doc = None

    standalone = n.get('standalone')

    if app_name != "global":
        f.write('''\
.. highlight:: rst

.. _%s:

%s
%s
%s

**%s**\n''' % (app_name, "#"*len(app_name), app_name, "#"*len(app_name), desc))

        if doc is not None and doc != "":
            f.write('''

Description
===========

%s
''' % doc)
    else:
        f.write(".. _%s:\n\n" % app_name)
        f.write(doc)

    options = xml_collect_options(n)
    plugins = app_plugin_nodes.get(app_name)
    if plugins:
        for p in plugins:
            name = p.get('name')
            desc_node = p.find('description')
            if desc_node is not None and desc_node.text is not None:
                desc = [l.strip() for l in desc_node.text.strip().replace(
                    "\r", "").split('\n')]
            else:
                desc = []
            poptions = xml_collect_options(p)
            if poptions:
                options += "\n.. _%s/%s:\n\n" % (app_name, name)
                title = name + " extension"
                options += '''
%s
%s

''' % (title, "-"*len(title))
                options += "\n".join(desc) + "\n\n"
                options += poptions

    if standalone and standalone.lower() == "true":
        if options:
            note = '''

.. note::

   %s is a :term:`standalone module` and does not inherit :ref:`global options <global-configuration>`.

''' % app_name

            cfgs = '''\
| :file:`etc/defaults/%s.cfg`
| :file:`etc/%s.cfg`
| :file:`~/.seiscomp/%s.cfg`

''' % (app_name, app_name, app_name)
        else:
            note = ""
            cfgs = ""
    else:
        note = ""
        if app_name != "global":
            cfgs = '''\
| :file:`etc/defaults/global.cfg`
| :file:`etc/defaults/%s.cfg`
| :file:`etc/global.cfg`
| :file:`etc/%s.cfg`
| :file:`~/.seiscomp/global.cfg`
| :file:`~/.seiscomp/%s.cfg`

%s inherits :ref:`global options<global-configuration>`.

''' % (app_name, app_name, app_name, app_name)
        else:
            cfgs = ""

    documented_plugins = []
    if plugins and len(plugins) > 0:
        for p in plugins:
            if p in plugins_with_ref:
                documented_plugins.append(p)

    if len(documented_plugins) > 0:
        f.write('''

Plugins
=======

''')

        for p in documented_plugins:
            name = p.get('name')
            desc_node = p.find('description')
            if desc_node is not None and desc_node.text is not None:
                desc = [l.strip() for l in desc_node.text.strip().replace(
                    "\r", "").split('\n')]
            else:
                desc = []

            f.write("* :ref:`%s <%s>`\n\n  %s\n" %
                    (name, plugins_with_ref[p], " ".join(desc)))

    if options or note or cfgs:
        f.write('''
.. _%s_configuration:

Module Configuration
====================
%s
%s
''' % (app_name, note, cfgs))

    if options:
        f.write(options)

    bindings = app_binding_nodes.get(app_name)
    bindings_options = ""
    if bindings:
        category_map = {}
        for b in bindings:
            category = b.get('category')
            if category:
                # Just remember category bindings and add them afterwards
                try:
                    category_map[category].append(b)
                except BaseException:
                    category_map[category] = [b]
                continue
            bindings_options += xml_collect_options(b)

        for cat, bindings in sorted(category_map.items()):
            names = []
            bindings = sorted(bindings, key=lambda n: n.get('name'))
            for b in bindings:
                names.append(b.get('name'))

            if len(names) == 0:
                continue

            bindings_options += ".. confval:: %s\n\n" % cat
            bindings_options += "   Type: *list:string*\n\n"
            bindings_options += "   Defines a list of extension bindings to be used.\n"
            bindings_options += "   Each binding can then be configured individually.\n\n"
            bindings_options += "   Available identifiers: %s\n\n" % " ".join(
                [":ref:`%s-%s-%s-label`" % (app_name, cat, name) for name in names])
            bindings_options += "   .. code-block:: sh\n\n"
            if len(names) >= 2:
                bindings_options += "      # param1 and param2 are just placeholders.\n"
                bindings_options += "      %s = %s, %s\n" % (
                    cat, names[0], names[1])
                bindings_options += "      %s.%s1.param1 = value11\n" % (
                    cat, names[0])
                bindings_options += "      %s.%s1.param2 = value12\n" % (
                    cat, names[0])
                bindings_options += "      %s.%s2.param1 = value21\n" % (
                    cat, names[1])
                bindings_options += "      %s.%s2.param2 = value22\n" % (
                    cat, names[1])
                bindings_options += "\n"
            bindings_options += "      # To use the same binding twice, aliases must be used.\n"
            bindings_options += "      # Aliases are created by prepending a unique name " \
                                "followed by a colon\n"
            bindings_options += "      %s = %s, %s_2:%s\n" % (
                cat, names[0], names[0], names[0])
            bindings_options += "      %s.%s.param1 = value11\n" % (
                cat, names[0])
            bindings_options += "      %s.%s.param2 = value12\n" % (
                cat, names[0])
            bindings_options += "      %s.%s_2.param1 = value21\n" % (
                cat, names[0])
            bindings_options += "      %s.%s_2.param2 = value22\n" % (
                cat, names[0])
            bindings_options += "\n"

            for b in bindings:
                name = b.get('name')
                bindings_options += "\n.. _%s-%s-%s-label:\n\n" % (
                    app_name, cat, name)
                bindings_options += "%s\n" % name
                bindings_options += "%s\n\n" % ('-'*len(name))
                desc = xml_desc_lines(b)
                if len(desc) > 0:
                    bindings_options += "\n".join(desc)
                    bindings_options += "\n"
                bindings_options += xml_collect_options(
                    b, cat + "." + name + ".")

        if bindings_options:
            f.write('''

Bindings Parameters
===================

''')

            binding_rst = get_app_binding_rst(doc_dirs, app_name)
            if binding_rst:
                bdoc = codecs.open(binding_rst, "r", "utf-8").read()
            else:
                bdoc = None

            if bdoc:
                f.write("%s\n\n" % bdoc)

            f.write('''
%s
''' % bindings_options)

    f.write(xml_collect_cmdline(n, False))


# Generate extensions.doc to give an overview over available extensions
filename = os.path.join(out_base_dir, "extensions.doc")
try:
    f = codecs.open(filename, "w", "utf-8")
except Exception as e:
    print("ERROR: unable to create _extensions.rst: {}".format(e),
          file=sys.stderr)
    sys.exit(1)

if len(app_plugin_nodes) > 0:
    table = []

    for key, nodes in list(app_plugin_nodes.items()):
        mod = ":ref:`%s<%s>`" % (key, key)
        plugs = []
        for node in nodes:
            ref = plugin_refs.get(node)
            if not ref:
                ref = "%s/%s" % (key, node.get('name'))
            plugs.append(":ref:`%s<%s>`" % (node.get('name'), ref))
        table.append([mod, " ".join(plugs)])

    col1_width = len("Module")
    col2_width = len("Extensions")
    for row in table:
        if len(row[0]) > col1_width:
            col1_width = len(row[0])
        if len(row[1]) > col2_width:
            col2_width = len(row[1])

    f.write("%s  %s\n" % ("="*col1_width, "="*col2_width))
    f.write("%*s  %*s\n" % (col1_width, "Module", col2_width, "Plugin's"))
    f.write("%s  %s\n" % ("="*col1_width, "="*col2_width))
    for row in table:
        f.write("%*s  %*s\n" % (col1_width, row[0], col2_width, row[1]))
    f.write("%s  %s\n" % ("="*col1_width, "="*col2_width))
else:
    f.write("**No extensions available**\n")

f = open(os.path.join(out_dir, "conf.py"), "a")
print("# -- Options for manual page output --------------------------------------------", file=f)
print("", file=f)
print("# One entry per manual page. List of tuples", file=f)
print("# (source start file, name, description, authors, manual section).", file=f)
print("man_pages = [", file=f)
for man_page in man_pages:
    author = "gempa GmbH, GFZ Potsdam"
    if man_page[1]:
        author = man_page[1]
    print("    ('apps/%s', '%s', project + u' Documentation', [u'%s'], 1)," % (
        man_page[0], man_page[0], author), file=f)
print("]", file=f)
print("", file=f)
f.close()


if build_html:
    print("Clean-up HTML build dir")
    try:
        shutil.rmtree(os.path.join(out_build_dir, "html"))
    except BaseException:
        pass

    r = os.WEXITSTATUS(
        os.system("sphinx-build -b html %s %s" % (
            out_dir, os.path.join(out_build_dir, "html"))))
    if r:
        sys.exit(r)

if build_man:
    print("Clean-up MAN build dir")
    try:
        shutil.rmtree(os.path.join(out_build_dir, "man1"))
    except BaseException:
        pass

    r = os.WEXITSTATUS(
        os.system("sphinx-build -b man %s %s" % (
            out_dir, os.path.join(out_build_dir, "man1"))))
    if r:
        sys.exit(r)

    print("Clean-up MAN temporary files")
    try:
        shutil.rmtree(os.path.join(out_build_dir, "man1", ".doctrees"))
    except BaseException:
        pass

if build_pdf:
    print("Clean-up PDF build dir")
    try:
        shutil.rmtree(os.path.join(out_build_dir, "pdf"))
    except BaseException:
        pass

    r = os.WEXITSTATUS(
        os.system("sphinx-build -M latexpdf %s %s" % (
            out_dir, os.path.join(out_build_dir, "pdf"))))
    if r:
        sys.exit(r)
