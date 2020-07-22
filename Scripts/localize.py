#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Localize.py - Incremental localization on XCode projects
# João Moreno 2009
# http://joaomoreno.com/

# Modified by Steve Streeting 2010 https://www.stevestreeting.com
# Changes
# - Use .strings files encoded as UTF-8
#   This is useful because Mercurial and Git treat UTF-16 as binary and can't
#   diff/merge them. For use on iPhone you can run an iconv script during build to
#   convert back to UTF-16 (Mac OS X will happily use UTF-8 .strings files).
# - Clean up .old and .new files once we're done

from sys import argv
from codecs import open
from re import compile
from copy import copy
import os

re_translation = compile(r'^"(.+)" = "(.+)";$')
re_comment_single = compile(r'^/\*.*\*/$')
re_comment_start = compile(r'^/\*.*$')
re_comment_end = compile(r'^.*\*/$')


ROOT_FOLDER = 'Simplenote'
BASE_FOLDER = 'Base.lproj'
ENGLISH_FOLDER = 'en.lproj'

MAIN_NIB_FILE = 'MainMenu.xib'

OUT_STRINGS_FILE = 'Localizable.strings'
NIB_STRINGS_FILE = 'InterfaceBuilder.strings'
SRC_STRINGS_FILE = 'Sources.strings'
TMP_STRINGS_FILE = "Temporary.strings"


class LocalizedString():
    def __init__(self, comments, translation):
        self.comments, self.translation = comments, translation
        self.key, self.value = re_translation.match(self.translation).groups()

    def __unicode__(self):
        return u'%s%s\n' % (u''.join(self.comments), self.translation)

    def overwriteKeyWithValue(self):
        old_key, old_value = re_translation.match(self.translation).groups()
        self.key = old_value
        self.translation = '"%s" = "%s";\n' % (old_value, old_value)


class LocalizedFile():
    def __init__(self, fname=None, auto_read=False):
        self.fname = fname
        self.strings = []
        self.strings_d = {}

        if auto_read:
            self.read_from_file(fname)

    def read_from_file(self, fname=None):
        fname = self.fname if fname == None else fname
        try:
            f = open(fname, encoding='utf_8', mode='r')
        except:
            print 'File %s does not exist.' % fname
            exit(-1)

        line = f.readline()
        while line:
            comments = [line]

            if not re_comment_single.match(line):
                while line and not re_comment_end.match(line):
                    line = f.readline()
                    comments.append(line)

            line = f.readline()
            if line and re_translation.match(line):
                translation = line
            else:
                raise Exception('invalid file')

            line = f.readline()
            while line and line == u'\n':
                line = f.readline()

            string = LocalizedString(comments, translation)
            self.strings.append(string)
            self.strings_d[string.key] = string

        f.close()

    def save_to_file(self, fname=None):
        fname = self.fname if fname == None else fname
        try:
            f = open(fname, encoding='utf_8', mode='w')
        except:
            print 'Couldn\'t open file %s.' % fname
            exit(-1)

        for string in self.strings:
            f.write(string.__unicode__())

        f.close()

    def update_with(self, new):
        output = LocalizedFile()

        for string in new.strings:
            if self.strings_d.has_key(string.key):
                new_string = copy(self.strings_d[string.key])
                new_string.comments = string.comments
                string = new_string

            output.strings.append(string)
            output.strings_d[string.key] = string

        return output

    def merge_with(self, new):
        output = LocalizedFile()
        output.strings = self.strings
        output.strings_d = self.strings_d

        for string in new.strings:
            if self.strings_d.has_key(string.key):
                continue

            output.strings.append(string)
            output.strings_d[string.key] = string

        return output

    def overwrite_keys_with_values(self):
        output = LocalizedFile()

        for string in self.strings:
            new_string = copy(string)
            new_string.overwriteKeyWithValue()
            output.strings_d[new_string.key] = new_string

        output.strings = output.strings_d.values()

        return output


def update(out_fname, old_fname, new_fname):
    try:
        old = LocalizedFile(old_fname, auto_read=True)
        new = LocalizedFile(new_fname, auto_read=True)
        output = old.update_with(new)
        output.save_to_file(out_fname)
    except:
        print 'Error: input files have invalid format.'


def merge(out_fname, lhs_fname, rhs_fname):
    try:
        lhs = LocalizedFile(lhs_fname, auto_read=True)
        rhs = LocalizedFile(rhs_fname, auto_read=True)
        output = lhs.merge_with(rhs)
        output.save_to_file(out_fname)
    except:
        print 'Error: input files have invalid format.'


# Updates a Localized.string file, so that the `key = value`
# We want to do this for a specific use case: NIB strings
#
# - Note: Result is guarranteed to contain unique entries! 
def overwrite_keys_with_values(fname):
    try:
        not_normalized = LocalizedFile(fname, auto_read=True)
        normalized = not_normalized.overwrite_keys_with_values()
        normalized.save_to_file(fname)
    except:
        print 'Error: input files have invalid format.'


def localize_sources(path):
    language = os.path.join(path, ENGLISH_FOLDER)
    original = merged = language + os.path.sep + OUT_STRINGS_FILE

    old = original + '.old'
    new = original + '.new'

    genstrings_cmd = 'genstrings -q -o "%s" `find ./Simplenote -name "*.m" -o -name "*.swift"`'

    if os.path.isfile(original):
        os.rename(original, old)
        os.system(genstrings_cmd % language)
        os.system('iconv -f UTF-16 -t UTF-8 "%s" > "%s"' % (original, new))
        update(merged, old, new)
    else:
        os.system(genstrings_cmd % language)
        os.rename(original, old)
        os.system('iconv -f UTF-16 -t UTF-8 "%s" > "%s"' % (old, original))

    if os.path.isfile(old):
        os.remove(old)
    if os.path.isfile(new):
        os.remove(new)


def localize_nibs(path):
    base_folder = os.path.join(path, BASE_FOLDER)
    en_folder   = os.path.join(path, ENGLISH_FOLDER)

    input_path  = os.path.join(base_folder, MAIN_NIB_FILE)
    tmp_path    = os.path.join(en_folder, TMP_STRINGS_FILE)
    output_path = os.path.join(en_folder, NIB_STRINGS_FILE)

    ibtool_cmd  = 'ibtool %s --generate-strings-file %s' % (input_path, tmp_path)
    utf_cmd     = 'iconv -f UTF-16 -t UTF-8 "%s" > "%s"' % (tmp_path, output_path)

    os.system(ibtool_cmd)
    os.system(utf_cmd)
    overwrite_keys_with_values(output_path)
    os.remove(tmp_path)


def merge_all_strings(path):
    en_folder = os.path.join(path, ENGLISH_FOLDER)
    nib_strings_path = os.path.join(en_folder, NIB_STRINGS_FILE)
    src_strings_path = os.path.join(en_folder, SRC_STRINGS_FILE)
    out_strings_path = os.path.join(en_folder, OUT_STRINGS_FILE)

    os.rename(out_strings_path, src_strings_path)

    merge(out_strings_path, nib_strings_path, src_strings_path)

    os.remove(nib_strings_path)
    os.remove(src_strings_path)


if __name__ == '__main__':
    root_path = os.path.join(os.getcwd(), ROOT_FOLDER)
    localize_sources(root_path)
    localize_nibs(root_path)
    merge_all_strings(root_path)

