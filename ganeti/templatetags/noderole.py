# -*- coding: utf-8 -*- vim:fileencoding=utf-8:
# Copyright (C) 2010-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from django import template

register = template.Library()

@register.filter
def noderole(value):
    if value == "M":
        return "Master"
    if value == "C":
        return "Candidate"
    if value == "R":
        return "Regular"
    if value == "D":
        return "Drained"
    if value == "O":
        return "Offline"

@register.filter
def nodelabel(value):
    if value == "M":
        return "success"
    if value == "C":
        return "info"
    if value == "R":
        return ""
    if value == "D":
        return "warning"
    if value == "O":
        return "important"
