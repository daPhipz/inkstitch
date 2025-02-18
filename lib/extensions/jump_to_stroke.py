# Authors: see git history
#
# Copyright (c) 2023 Authors
# Licensed under the GNU GPL version 3.0 or later.  See the file LICENSE for details.

from inkex import (Boolean, DirectedLineSegment, Path, PathElement, Transform,
                   errormsg)

from ..elements import Stroke
from ..i18n import _
from ..svg import PIXELS_PER_MM, get_correction_transform
from ..svg.tags import INKSTITCH_ATTRIBS, SVG_GROUP_TAG
from .base import InkstitchExtension


class JumpToStroke(InkstitchExtension):
    """Adds a running stitch as a connection between two (or more) selected elements.
       The elements must have the same color and a minimum distance (collapse_len)."""

    def __init__(self, *args, **kwargs):
        InkstitchExtension.__init__(self, *args, **kwargs)
        self.arg_parser.add_argument("--tab")

        self.arg_parser.add_argument("-i", "--minimum-jump-length", type=float, default=3.0, dest="min_jump")
        self.arg_parser.add_argument("-a", "--maximum-jump-length", type=float, default=0, dest="max_jump")
        self.arg_parser.add_argument("--connect", type=str, default="all", dest="connect")
        self.arg_parser.add_argument("--exclude-trim", type=Boolean, default=True, dest="exclude_trim")
        self.arg_parser.add_argument("--exclude-stop", type=Boolean, default=True, dest="exclude_stop")
        self.arg_parser.add_argument("--exclude-force-lock-stitch", type=Boolean, default=True, dest="exclude_forced_lock")

        self.arg_parser.add_argument("-m", "--merge", type=Boolean, default=False, dest="merge")
        self.arg_parser.add_argument("-l", "--stitch-length", type=float, default=2.5, dest="running_stitch_length_mm")
        self.arg_parser.add_argument("-t", "--tolerance", type=float, default=2.0, dest="running_stitch_tolerance_mm")

    def effect(self):
        if not self.svg.selection or not self.get_elements() or len(self.elements) < 2:
            errormsg(_("Please select at least two elements to convert the jump stitch to a running stitch."))
            return

        last_group = None
        last_layer = None
        last_element = None
        last_stitch_group = None
        for element in self.elements:
            group = None
            layer = None
            for ancestor in element.node.iterancestors(SVG_GROUP_TAG):
                if group is None:
                    group = ancestor
                if ancestor.groupmode == "layer":
                    layer = ancestor
                    break

            stitch_group = element.to_stitch_groups(last_stitch_group)

            if (last_stitch_group is None or
                    element.color != last_element.color or
                    (self.options.connect == "layer" and last_layer != layer) or
                    (self.options.connect == "group" and last_group != group) or
                    (self.options.exclude_trim and (last_element.has_command("trim") or last_element.trim_after)) or
                    (self.options.exclude_stop and (last_element.has_command("stop") or last_element.stop_after)) or
                    (self.options.exclude_forced_lock and last_element.force_lock_stitches)):
                last_layer = layer
                last_group = group
                last_stitch_group = stitch_group[-1]
                last_element = element
                continue

            start = last_stitch_group.stitches[-1]
            end = stitch_group[-1].stitches[0]
            self.generate_stroke(last_element, element, start, end)

            last_group = group
            last_layer = layer
            last_stitch_group = stitch_group[-1]
            last_element = element

    def generate_stroke(self, last_element, element, start, end):
        node = element.node
        parent = node.getparent()
        index = parent.index(node)

        # do not add a running stitch if the distance is smaller than min_jump setting
        line = DirectedLineSegment((start.x, start.y), (end.x, end.y))
        if line.length < self.options.min_jump * PIXELS_PER_MM:
            return
        # do not add a running stitch if the distance is longer than max_jump setting
        if self.options.max_jump > 0 and line.length > self.options.max_jump * PIXELS_PER_MM:
            return

        path = Path([(start.x, start.y), (end.x, end.y)])
        # option: merge line with paths
        merged = False
        if self.options.merge and isinstance(last_element, Stroke) and last_element.node.TAG == "path":
            path.transform(Transform(get_correction_transform(last_element.node)), True)
            path = last_element.node.get_path() + path[1:]
            last_element.node.set('d', str(path))
            path.transform(-Transform(get_correction_transform(last_element.node)), True)
            merged = True
        if self.options.merge and isinstance(element, Stroke) and node.TAG == "path":
            path.transform(Transform(get_correction_transform(node)), True)
            path = path + node.get_path()[1:]
            node.set('d', str(path))
            if merged:
                # remove last element (since it is merged)
                last_parent = last_element.node.getparent()
                last_parent.remove(last_element.node)
                # remove parent group if empty
                if len(last_parent) == 0:
                    last_parent.getparent().remove(last_parent)
            return

        if merged:
            return

        # add simple stroke to connect elements
        path.transform(Transform(get_correction_transform(node)), True)
        color = element.color
        style = f'stroke:{color};stroke-width:1px;stroke-dasharray:3, 1;fill:none;'

        line = PathElement(d=str(path), style=style)
        line.set(INKSTITCH_ATTRIBS['running_stitch_length_mm'], self.options.running_stitch_length_mm)
        line.set(INKSTITCH_ATTRIBS['running_stitch_tolerance_mm'], self.options.running_stitch_tolerance_mm)
        parent.insert(index, line)


if __name__ == '__main__':
    JumpToStroke().run()
