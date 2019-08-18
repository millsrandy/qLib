"""
        @file       qlibutils.py
        @author     xy
        @since      2012-07-23

        @brief      qLib-related utility functions.
"""

import hou

import glob
import os
import platform
import re
import subprocess
import traceback

# for paste_clipboard_to_netview()
from hutil import Qt
import nodegraphutils


# TODO: msg functions with exception handling


def is_platform(name='none'):
    return name.lower() in platform.system().lower()

def is_linux():
    return is_platform('linux')

def is_windows():
    return is_platform('win')

def is_mac():
    return is_platform('mac')



def statmsg(msg, warn=False):
    """.
    """
    s = hou.severityType.Warning if warn else hou.severityType.Message
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(msg, severity=s)


def set_namespace_aliases(prefix="qLib::", alias=True, verbose=False):
    """Defines (non-)namespaced aliases for operators with a particular namespace prefix.

    This is used for always creating the namespaced versions of assets, even if an
    older .hip file contains non-namespaced asset names.

    Mapping looks like:  <opname>  -->  <prefix>::<opname>::<version>


    @note
            IMPORTANT: Although the manual says it's fine to omit the version of a
            namespaced asset (and that would refer to the latest version),
            omitting it results in files getting messed up when loaded,
            so version numbers _are_ included in the opaliases.

    @note
            This function should be called (preferably) on Houdini startup, e.g.

            import qlibutils
            qlibutils.set_namespace_aliases( ["qLib::", "myStuff::"] )

    @todo
            For each asset, the highest version number should be found and used.
            Right now it uses the first version it founds (which is fine for now).
    """
    if type(prefix) is list:
        for p in prefix:
            set_namespace_aliases(p)
        return

    assert "::" in prefix, "Include trailing '::' characters in prefix"

    cmds = []
    for file in hou.hda.loadedFiles():

        names = [(d.nodeType().name(), d.nodeTypeCategory().name())
                 for d in list(hou.hda.definitionsInFile(file))
                 if prefix in d.nodeType().name()]

        for n in names:

            try:
                # strip namespace prefix and version suffix
                old = re.sub("^[^:]+::", "", n[0])
                old = re.search("^[^:]+", old).group(0)

                # opalias <network> <namespaced-op.> <plain-old-op.>
                cmd = "opalias %s %s %s" % (n[1], n[0], old)

                if cmd not in cmds:
                    if verbose:
                        print cmd
                    if alias:
                        hou.hscript(cmd)
                    cmds.append(cmd)
                else:
                    print "# ALREADY ALIASED: %s (%s)" % (cmd, file)

            except:
                print "ERROR: %s" % traceback.format_exc()


def to_clipboard(contents="", env=None):
    """Copies the specified string to the system clipboard.

    @note
            - Linux only at the moment
            - requires xclip to be installed

    @todo
            Make it work under other OSs than linux?
    """
    try:
        contents = str(contents)
        if env:
            contents = str(hou.getenv(env))
        hou.ui.copyTextToClipboard(contents)
    except:
        pass


def do_crash_recovery(calledFromUI=False):
    """Performs crash recovery from an emergency-saved file.
    """
    tmpdir = str(hou.getenv("TEMP") or hou.getenv("HOUDINI_TEMP_DIR"))
    files = glob.glob(os.path.join(tmpdir, '*.hip'))

    uicall = calledFromUI

    if hou.isUIAvailable() and len(files) > 0:

        td = os.path.join(tmpdir, '')  # dir with '/'
        files = [(f, os.path.getmtime(f), ) for f in files]
        files = sorted(files, key=lambda f: f[1], reverse=True)
        files = [str(re.sub('^%s' % td, '', f[0])) for f in files]

        sel = hou.ui.selectFromList(files, exclusive=True,
                                    title="Crash Recovery",
                                    message="Select .hip File to Recover")

        recovered = False
        if len(sel) > 0:
            f = files[sel[0]]
            fn = os.path.join(tmpdir, f)

            # extract HIPNAME
            f = re.sub('^crash.', '', f)
            f = re.sub('\..+_[0-9]+\.hip', '.hip', f)

            # do recovery
            try:
                hou.hipFile.clear(True)
                hou.hipFile.load(fn, True)
                hou.setUpdateMode(hou.updateMode.Manual)
                recovered = True
            except:
                hou.ui.setStatusMessage(
                    "error while recovering file %s" % fn, hou.severityType.Error)
                print "ERROR: %s" % traceback.format_exc()

            hou.hipFile.setName(f)

        # delete crash file(s)

        msg = 'Cleanup: Delete all crash recovery hip files?'
        if recovered:
            msg = \
                'File recovered. Make sure to save it to a safe location.\n' \
                'NOTE: Update mode is set to "Manual" to avoid potential re-crashes.\n' \
                '\n%s' % msg

        d = hou.ui.displayMessage(msg, buttons=("DELETE", "Skip", ))
        if d == 0:
            files = \
                glob.glob(os.path.join(tmpdir, 'crash.*')) + \
                glob.glob(os.path.join(tmpdir, '*.hip'))
            for f in files:
                try:
                    os.remove(f)
                except:
                    pass

            hou.ui.setStatusMessage(
                "crash recovery cleanup: deleted %d files" % len(files))
        else:
            pass  # user cancelled

    else:
        # no crash files found
        #
        if uicall:
            hou.ui.setStatusMessage(
                '  Crash Recovery:  No emergency-saved .hip file(s) found -- nothing to recover. (%s)' % tmpdir, hou.severityType.ImportantMessage)
            pass


def open_dir(dir="", env=None):
    """Opens the specified directory in the system file browser.
    """
    dir = str(dir)

    if env:
        dir = str(hou.getenv(env))

    if not os.path.exists(dir):
        statmsg("Directory doesn't exist (%s)" % dir, warn=True)
        return

    if is_linux():
        statmsg("(linux) xdg-open %s" % dir)
        subprocess.call(["xdg-open", dir])

    if is_windows():
        dir = dir.replace('/', '\\')
        statmsg("(windows) start %s" % dir)
        subprocess.call(["start", dir])

    if is_mac():
        statmsg("(mac) open %s" % dir)
        subprocess.call(["open", dir])


def get_hda_paths(nodes):
    """Finds filesystem paths for specified HDAs.
    """
    hdas = []
    for node in nodes:
        d = node.type().definition()
        if d:
            path = d.libraryFilePath()
            if path != 'Embedded':
                hdas.append(path)
    return hdas


def open_hda_dirs():
    """Opens folders for the selected HDAs.
    """
    hdas = get_hda_paths(hou.selectedNodes())
    dirs = set()

    for h in hdas:
        dirs.add(os.path.split(h)[0])

    for d in dirs:
        open_dir(d)


def hdapath_to_clipboard():
    """Copies the full path of the first selected HDA to the clipboard.
    """
    hdas = get_hda_paths(hou.selectedNodes())
    hdas = '\n'.join(hdas)
    to_clipboard(hdas)


def nodes_to_clipboard(fullPaths=False, hdaTypeNames=False):
    """Copies the names or full paths of selected nodes to the clipboard.
    """
    sep = '\n' if fullPaths else ' '
    nodes = hou.selectedNodes()

    func = lambda n: n.name()

    if hdaTypeNames:
        func = lambda n: n.type().name()

    if fullPaths:
            func = lambda n: n.path()
            if hdaTypeNames:
                func = lambda n: "%s (%s)" % (n.path(), n.type().name(), )

    text = sep.join([ func(n) for n in nodes ])
    to_clipboard(text)


def toggle_abs_rel_path(kwargs):
    """Converts between absolute and relative OP paths.
    (Called from PARMmenu.xml)
    """
    if 'parms' in kwargs:
        for parm in kwargs['parms']:
            try:
                node = parm.node()
                path = parm.evalAsString()

                target = node.node(path)

                path_rel = node.relativePathTo(target)
                path_abs = target.path()

                r = path_rel if path==path_abs else path_abs

                parm.set(r)
            except:
                pass


def add_parm_value_multiplier(kwargs, add_exponent=False):
    """Adds a value/multipler parameter pair to the specified parameter.
    (Called from PARMmenu.xml)
    """
    p = kwargs['parms'][0]
    try:
        n = p.node()

        v = p.eval()
        t = p.parmTemplate()
        g = n.parmTemplateGroup()

        pn = t.name()
        pl = t.label()
        pvn = '%s_value' % pn
        pmn = '%s_mult' % pn
        pxn = '%s_exp' % pn
        t = hou.FloatParmTemplate(name=p.name(), label="...", num_components=1)

        expr = "ch('%s') * ch('%s')" % (pvn, pmn, )

        if not n.parm(pvn) and not n.parm(pmn):
            # value
            t.setName(pvn)
            t.setLabel('%s (v)' % pl)
            t.setDefaultValue( (v, ) )
            g.insertAfter(pn, t)
            # mult
            t.setName(pmn)
            t.setLabel('%s (%%)' % pl)
            t.setMinValue(0.0)
            t.setMaxValue(2.0)
            t.setDefaultValue( (1.0, ) )
            g.insertAfter(pvn, t)

            if add_exponent and not n.parm(pxn):
                # exp
                t.setName(pxn)
                t.setLabel('%s (exp)' % pl)
                t.setMinValue(0.001)
                t.setMaxValue(4.0)
                t.setDefaultValue( (2.0, ) )
                g.insertAfter(pmn, t)

                expr = "ch('%s') * pow(ch('%s'), ch('%s'))" % (pvn, pmn, pxn, )

            # add parms
            n.setParmTemplateGroup(g)

            p.setExpression(expr)
        else:
            hou.ui.setStatusMessage("Value/multiplier params already exist for %s" % p.path(),
                severity=hou.severityType.Warning)
    except:
        hou.ui.setStatusMessage("couldn't set up value/multiplier parameters on %s" % p.path(),
            severity=hou.severityType.Error)


def set_ramp_basis(kwargs, ramp_basis):
    """Set all knots on a ramp to the specified type.
    (Called from PARMmenu.xml)
    """
    try:
        p = kwargs['parms'][0]
        v = p.eval()
        num_keys = len(v.basis())
        new_basis = (ramp_basis, ) * num_keys
        new_ramp = hou.Ramp(new_basis, v.keys(), v.values())
        p.set(new_ramp)
    except:
        hou.ui.setStatusMessage("couldn't set ramp interpolation type on %s" % p.path(),
            severity=hou.severityType.Error)


def find_camera(oppattern, path=None):
    """Finds a camera OBJ within nested subnets and returns its full path.
    """
    r = ''
    try:
        root = hou.pwd()
        if path:
            root = hou.node(path)
        root = root.glob(oppattern)

        if len(root) > 0:
            cam = [n.path() for n in root[0].allSubChildren()
                   if n.type().name() == 'cam']
            if len(cam) > 0:
                r = cam[0]
            else:
                pass  # no camera found
        else:
            pass  # no root node found

    except:
        pass  # TODO: error handling

    return r


def backup_rop_output_file():
    """Creates a dated backup of an output file of a ROP.
    Useful as a ROP Pre-Render call.
    """
    pass


def remove_embedded_hdas():
    """Remove all embedded HDAs from the scene.
    """

    do_it = hou.ui.displayMessage(
        "Remove all Embdedded HDAs (OTLs) from the current scene?\n"
        "Warning: This cannot be undone!",
        buttons=("Ok", "Cancel", ),
        default_choice=1, close_choice=1)

    if do_it==0:
        hou.hda.uninstallFile("Embedded")


def find_same_nodes(nodes):
    """Find the same node types in a network.
    """

    def type_name(n):
        """Build a (not exactly correct) full typename (but without the asset version)."""
        return "::".join(n.type().nameComponents()[0:-1])

    r = []
    types = set()
    for n in nodes:
        types.add(type_name(n))

    all = nodes[0].parent().children()
    r = [ n for n in all if type_name(n) in types ]
    return r


def get_netview_path(kwargs):
    """Finds the path of the current network view from kwargs.
    """
    if "editor" in kwargs:
        return kwargs["editor"].pwd()
    else:
        # TODO: raise an error
        return None


def add_to_selection(nodes, kwargs):
    """Extends the current node selection with 'nodes', according to
    the modifier keys in kwargs.

    no modifier:    replace selection
    shift:          add to selection
    ctrl:           remove from selection
    ctrl+shift:     intersect with selection
    """
    haz_shift = kwargs["shiftclick"] or kwargs['altclick']
    haz_ctrl = kwargs["ctrlclick"]

    current = set(hou.selectedNodes())
    sel = set(nodes)

    if haz_shift or haz_ctrl:
        # we got some modifier pressed
        if haz_shift:
            if haz_ctrl:
                # shift+ctrl: intersection
                sel = sel.intersection(current)
            else:
                # shift: union
                sel = sel.union(current)
        else:
            # ctrl: remove from selection
            sel = current.difference(sel)

    if sel is not None:
        hou.clearAllSelected()
        for n in sel:
            n.setSelected(True)


def is_node_locked(node):
    """Check if node is locked. Implementation level LOL.
    """
    r = False
    if "isHardLocked" in dir(node):
        r = node.isHardLocked()
    elif "isLocked" in dir(node):
        r = node.isLocked()
    return r


def has_embedded_def(node):
    """Check if the node's HDA definition is Embedded.
    """
    d = node.type().definition()
    r = d and d.libraryFilePath() == "Embedded"
    return r


def select_netview_nodes(kwargs, criteria):
    """.
    """
    path = get_netview_path(kwargs)
    sel = [ n for n in path.children() if criteria(n) ]
    add_to_selection(sel, kwargs)



def paste_clipboard_to_netview(kwargs):
    """Paste clipboard contents (text or image) into the network editor.
    """
    clipboard = Qt.QtGui.QGuiApplication.clipboard()
    image = clipboard.image()
    text = clipboard.text()
    pane = kwargs.get('editor', None)

    if pane:
        pwd = pane.pwd()

        if image.isNull():
            # paste text (if any)
            if text!="":
                note = pwd.createStickyNote()
                note.move(pane.visibleBounds().center())
                s = note.size()
                s = hou.Vector2((s.x()*1.5, s.y()*0.5, ))
                note.setText(text)
                note.setSize(s)
        else:
            # paste image

            # TODO: generate automatic name
            image_name = ''
            ok, image_name = hou.ui.readInput('Enter name of image to be pasted:',
                buttons=('Ok', 'Cancel', ), close_choice=1,
                initial_contents=image_name)
            if image_name=='':
                ok = 1
            image_name += '.png'

            if ok==0:
                category = hou.objNodeTypeCategory()
                hda_typename = 'qLib::embedded_images'
                embedded = 'Embedded'
                hda_def = hou.hdaDefinition(category, hda_typename, embedded)
                
                # create hda definition if doesn't exist
                if not hda_def:
                    temp_node = hou.node('/obj').createNode('subnet')
                    hda_node = temp_node.createDigitalAsset(name=hda_typename, save_as_embedded=True)
                    hda_node.destroy()
        
                hda_def = hou.hdaDefinition(category, hda_typename, embedded)
        
                # create an instance in /obj if doesn't exist
                node = None
                nodes = [ n for n in hou.node('/obj').children() if n.type().name()==hda_typename ]
                
                if len(nodes)==0:
                    node = hou.node('/obj').createNode(hda_typename, node_name="embedded_images")
        
                # add clipboard image to hda definition (as section)
                ba = Qt.QtCore.QByteArray();
                buffer = Qt.QtCore.QBuffer(ba)
                buffer.open(Qt.QtCore.QIODevice.WriteOnly)
                image.save(buffer, "png")       
                buffer.close()
                hda_def.addSection(image_name, str(buffer.data()))
                
                # add image to network view
                image = hou.NetworkImage("opdef:/qLib::Object/embedded_images?%s" % image_name)
                image.setBrightness(0.75)
                #image.setRect(hou.BoundingRect(0, 0, 5, 2))
                s = pane.visibleBounds()
                center = s.center()
                s.translate(-center)
                s.scale((0.25, 0.25, ))
                s.translate(center)
                image.setRect(s)

                images = nodegraphutils.loadBackgroundImages(pwd)
                images.append(image)
                pane.setBackgroundImages(images)
                nodegraphutils.saveBackgroundImages(pwd, images)

