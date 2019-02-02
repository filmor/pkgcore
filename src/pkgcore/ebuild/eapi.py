# Copyright: 2011 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD 3 clause

import os
import re
import sys

from snakeoil import mappings, weakrefs, klass
from snakeoil.demandload import demandload, demand_compile_regexp
from snakeoil.osutils import pjoin

demandload(
    "functools:partial",
    'snakeoil.process.spawn:bash_version,spawn_get_output',
    "pkgcore.ebuild:atom,const",
    "pkgcore.log:logger",
)

demand_compile_regexp(
    '_valid_EAPI_regex', r"^[A-Za-z0-9_][A-Za-z0-9+_.-]*$"
)


eapi_optionals = mappings.ImmutableDict({
    # Controls what version of bash compatibility to force; see PMS.
    "bash_compat": '3.2',

    # Controls whether -r is allowed for dodoc.
    "dodoc_allow_recursive": False,

    # Controls whether doins recurses symlinks.
    "doins_allow_symlinks": False,

    # Controls the language awareness of doman; see PMS.
    "doman_language_detect": False,

    # Controls whether -i18n option is allowed.
    "doman_language_override": False,

    # Controls --disable-silent-rules passing for econf.
    'econf_disable_silent_rules': False,

    # Controls --disable-dependency-tracking passing for econf.
    'econf_disable_dependency_tracking': False,

    # Controls --docdir and --htmldir passing for econf; see PMS.
    'econf_docdir_and_htmldir': False,

    # Controls --sysroot passing for econf; see PMS.
    'econf_sysroot': False,

    # Controls whether an ebuild_phase function exists for ebuild consumption.
    'ebuild_phase_func': False,

    # Controls whether REPLACING vars are exported to ebuilds; see PMS.
    "exports_replacing": False,

    # Controls of whether failglob is enabled globally; see PMS.
    "global_failglob": False,

    # Controls whether MERGE vars are exported to ebuilds; see PMS.
    "has_merge_type": False,

    # Controls whether PORTDIR and ECLASSDIR are exported to ebuilds; see PMS.
    "has_portdir": True,

    # Controls whether ROOT, EROOT, D, and ED end with a trailing slash; see PMS.
    "trailing_slash": os.sep,

    # Controls whether SYSROOT, ESYSROOT, and BROOT are defined; see PMS.
    "has_sysroot": False,

    # Controls whether package.provided files in profiles are supported; see PMS.
    "profile_pkg_provided": True,

    # Controls whether package.mask and other files in profiles can
    # be directories; see PMS.
    "has_profile_data_dirs": False,

    # Controls whether REQUIRED_USE is supported, enforcing constraints on
    # allowed use configuration states.
    "has_required_use": False,

    # Controls whether USE dependency defaults are supported, see PMS.
    "has_use_dep_defaults": False,

    # Controls whether ENV_UNSET is supported, see PMS.
    "has_env_unset": False,

    # Controls whether AA env var is exported to ebuilds; this is a flattened
    # listing of each filename in SRC_URI.
    "has_AA": True,

    # Controls whether KV (kernel version; see PMS for details) is exported.
    "has_KV": True,

    # Controls whether or not pkgcore, or extensions loaded, actually fully
    # support this EAPI.
    'is_supported': True,

    # Controls whether IUSE defaults are supported; see PMS.
    'iuse_defaults': False,

    # Controls whether new* style bash functions can take their content input
    # from stdin, rather than an explicit ondisk file.
    'new_reads_stdin': False,

    # Controls whether utilities die on failure; see PMS.
    'nonfatal': True,

    # Controls whether die supports a nonfatal option; see PMS.
    "nonfatal_die": False,

    # Controls whether this EAPI supports prefix related variables/settings;
    # prefix awareness basically. See PMS for full details.
    "prefix_capable": False,

    # Controls whether profile-defined IUSE injection is supported.
    "profile_iuse_injection": False,

    # Controls whether profiles support package.use.stable.* and use.stable.* files.
    "profile_stable_use": False,

    # Controls whether SLOT values can actually be multi-part; see PMS EAPI 5.
    # This is related to ABI breakage detection.
    'sub_slotting': False,

    # Controls whether REQUIRED_USE supports the ?? operator.
    'required_use_one_of': False,

    # Controls whether SRC_URI supports the '->' operator for url filename renaming.
    "src_uri_renames": False,

    # Controls whether or not use dependency atoms are able to control their enforced
    # value relative to another; standard use deps just enforce either on or off; EAPIs
    # supporting this allow syntax that can enforce (for example) X to be on if Y is on.
    # See PMS EAPI 4 for full details.
    "transitive_use_atoms": False,

    # Controls whether or DEFINED_PHASES is mandated for this EAPI; if so, then we can
    # trust the cache definition and skip invoking those phases if they're not defined.
    # If the EAPI didn't mandate this var, then we can do our inference, but generally will
    # invoke the phase in the absense of that metadata var since we have no other choice.
    "trust_defined_phases_cache": False,

    # Controls whether unpack supports absolute paths; see PMS.
    "unpack_absolute_paths": False,

    # Controls whether unpack supports absolute paths; see PMS.
    "unpack_case_insensitive": False,

    # Controls whether user patches are supported.
    "user_patches": False,
})


class _optionals_cls(mappings.ImmutableDict):

    mappings.inject_getitem_as_getattr(locals())


class EAPI(object, metaclass=klass.immutable_instance):

    known_eapis = weakrefs.WeakValCache()
    unknown_eapis = weakrefs.WeakValCache()

    def __init__(self, magic, parent=None, phases=(), default_phases=(),
                 metadata_keys=(), mandatory_keys=(),
                 tracked_attributes=(), archive_suffixes=(),
                 optionals=None, ebd_env_options=None):
        sf = object.__setattr__

        sf(self, "_magic", str(magic))
        sf(self, "_parent", parent)

        sf(self, "phases", mappings.ImmutableDict(phases))
        sf(self, "phases_rev", mappings.ImmutableDict((v, k) for k, v in
           self.phases.items()))

        # We track the phases that have a default implementation- this is
        # primarily due to DEFINED_PHASES cache values not including it.
        sf(self, "default_phases", frozenset(default_phases))

        sf(self, "mandatory_keys", frozenset(mandatory_keys))
        sf(self, "metadata_keys", frozenset(metadata_keys))
        sf(self, "tracked_attributes", frozenset(tracked_attributes))
        sf(self, "archive_suffixes", frozenset(archive_suffixes))
        sf(self, "archive_suffixes_re", '(?:%s)' % '|'.join(map(re.escape, archive_suffixes)))

        if optionals is None:
            optionals = {}
        sf(self, 'options', _optionals_cls(optionals))
        if ebd_env_options is None:
            ebd_env_options = ()
        sf(self, "_ebd_env_options", ebd_env_options)

    @classmethod
    def register(cls, *args, **kwds):
        eapi = cls(*args, **kwds)
        pre_existing = cls.known_eapis.get(eapi._magic)
        if pre_existing is not None:
            raise ValueError(
                f"EAPI '{eapi}' is already known/instantiated- {pre_existing!r}")

        if (getattr(eapi.options, 'bash_compat', False) and
                bash_version() < eapi.options.bash_compat):
            # hard exit if the system doesn't have an adequate bash installed
            raise SystemExit(
                f"EAPI '{eapi}' requires >=bash-{eapi.options.bash_compat}, "
                f"system version: {bash_version()}")
        cls.known_eapis[eapi._magic] = eapi
        return eapi

    @klass.jit_attr
    def is_supported(self):
        """Check if an EAPI is supported."""
        if EAPI.known_eapis.get(self._magic) is not None:
            if not self.options.is_supported:
                logger.warning(f"EAPI '{self}' isn't fully supported")
                sys.stderr.flush()
            return True
        return False

    @klass.jit_attr
    def bash_funcs(self):
        """Internally implemented EAPI specific functions to skip when exporting."""
        try:
            with open(pjoin(const.EBD_PATH, 'funcnames', self._magic), 'r') as f:
                funcs = f.readlines()
        except FileNotFoundError:
            # we're running in the git repo and need to generate the list on the fly
            ret, funcs = spawn_get_output(
                [pjoin(const.EBD_PATH, 'generate_eapi_func_list'), self._magic])
            if ret != 0:
                raise Exception(
                    f"failed to generate list of EAPI '{self}' specific functions")
        return tuple(x.strip() for x in funcs)

    @klass.jit_attr
    def atom_kls(self):
        return partial(atom.atom, eapi=self._magic)

    def interpret_cache_defined_phases(self, sequence):
        phases = set(sequence)
        if not self.options.trust_defined_phases_cache:
            if not phases:
                # run them all; cache was generated
                # by a pm that didn't support DEFINED_PHASES
                return frozenset(self.phases)

        phases.discard("-")
        return frozenset(phases)

    def __str__(self):
        return self._magic

    @property
    def inherits(self):
        """Yield an EAPI's inheritance tree.

        Note that this assumes a simple, linear inheritance tree.
        """
        yield self
        parent = self._parent
        while parent is not None:
            yield parent
            parent = parent._parent

    @klass.jit_attr
    def helpers(self):
        """Directories for EAPI specific helpers to add to $PATH."""
        dirs = []
        for eapi in self.inherits:
            helper_dir = pjoin(const.EBUILD_HELPERS_PATH, eapi._magic)
            if os.path.exists(helper_dir):
                dirs.append(helper_dir)
        dirs.append(pjoin(const.EBUILD_HELPERS_PATH, 'common'))
        return tuple(dirs)

    @klass.jit_attr
    def ebd_env(self):
        """Dictionary of EAPI options passed to the ebd environment."""
        d = {}
        for k in self._ebd_env_options:
            d[f"PKGCORE_{k.upper()}"] = str(getattr(self.options, k)).lower()
        d["EAPI"] = self._magic
        return mappings.ImmutableDict(d)


def get_eapi(magic, suppress_unsupported=True):
    """Return EAPI object for a given identifier."""
    if _valid_EAPI_regex.match(magic) is None:
        eapi_str = f" {magic!r}" if magic else ''
        raise ValueError(f'invalid EAPI{eapi_str}')
    eapi = EAPI.known_eapis.get(magic)
    if eapi is None and suppress_unsupported:
        eapi = EAPI.unknown_eapis.get(magic)
        if eapi is None:
            eapi = EAPI(magic=magic, optionals={'is_supported': False})
            EAPI.unknown_eapis[eapi._magic] = eapi
    return eapi


def _shorten_phase_name(func_name):
    if func_name.startswith(('src_', 'pkg_')):
        return func_name[4:]
    return func_name


def _mk_phase_func_map(*sequence):
    return {_shorten_phase_name(x): x for x in sequence}


def _combine_dicts(*mappings):
    return {k: v for d in mappings for k, v in d.items()}


# Note that pkg_setup is forced by default since this is how our env setup occurs.
common_default_phases = tuple(
    _shorten_phase_name(x) for x in
    ("pkg_setup", "src_unpack", "src_compile", "src_test", "pkg_nofetch"))

common_phases = (
    "pkg_setup", "pkg_config", "pkg_info", "pkg_nofetch",
    "pkg_prerm", "pkg_postrm", "pkg_preinst", "pkg_postinst",
    "src_unpack", "src_compile", "src_test", "src_install")

common_mandatory_metadata_keys = (
    "DESCRIPTION", "HOMEPAGE", "IUSE",
    "KEYWORDS", "LICENSE", "SLOT", "SRC_URI")

common_metadata_keys = common_mandatory_metadata_keys + (
    "DEPEND", "RDEPEND", "PDEPEND", "RESTRICT",
    "DEFINED_PHASES", "PROPERTIES", "EAPI")

common_tracked_attributes = (
    "cflags", "cbuild", "chost", "ctarget", "cxxflags", "defined_phases",
    "bdepend", "depend", "rdepend", "pdepend",
    "description", "eapi", "distfiles", "fullslot", "homepage", "inherited",
    "iuse", "keywords", "ldflags", "license", "properties",
    "restrict", "source_repository",
)

common_archive_suffixes = (
    "tar",
    "tar.gz", "tgz", "tar.Z", "tar.z",
    "tar.bz2", "tbz2", "tbz",
    "zip", "ZIP", "jar",
    "gz", "Z", "z",
    "bz2",
    "rar", "RAR",
    "lha", "LHa", "LHA", "lzh",
    "a", "deb",
    "tar.lzma",
    "lzma",
    "7z", "7Z",
)

# Boolean variables exported to the bash side, e.g. ebuild_phase_func is
# exported as PKGCORE_EBUILD_PHASE_FUNC.
common_env_optionals = (
    "bash_compat", "dodoc_allow_recursive", "doins_allow_symlinks",
    "doman_language_detect", "doman_language_override", "ebuild_phase_func",
    "econf_disable_dependency_tracking", "econf_disable_silent_rules",
    "econf_docdir_and_htmldir", "econf_sysroot", "global_failglob",
    "new_reads_stdin", "nonfatal", "nonfatal_die", "profile_iuse_injection",
    "unpack_absolute_paths", "unpack_case_insensitive",
)

eapi0 = EAPI.register(
    magic="0",
    parent=None,
    phases=_mk_phase_func_map(*common_phases),
    default_phases=_mk_phase_func_map(*common_default_phases),
    metadata_keys=common_metadata_keys,
    mandatory_keys=common_mandatory_metadata_keys,
    tracked_attributes=common_tracked_attributes,
    archive_suffixes=common_archive_suffixes,
    optionals=eapi_optionals,
    ebd_env_options=common_env_optionals,
)

eapi1 = EAPI.register(
    magic="1",
    parent=eapi0,
    phases=eapi0.phases,
    default_phases=eapi0.default_phases,
    metadata_keys=eapi0.metadata_keys,
    mandatory_keys=eapi0.mandatory_keys,
    tracked_attributes=eapi0.tracked_attributes,
    archive_suffixes=eapi0.archive_suffixes,
    optionals=_combine_dicts(eapi0.options, dict(
        iuse_defaults=True,
    )),
    ebd_env_options=eapi0._ebd_env_options,
)

eapi2 = EAPI.register(
    magic="2",
    parent=eapi1,
    phases=_combine_dicts(
        eapi1.phases, _mk_phase_func_map("src_prepare", "src_configure")),
    default_phases=eapi1.default_phases.union(
        list(map(_shorten_phase_name, ["src_prepare", "src_configure"]))),
    metadata_keys=eapi1.metadata_keys,
    mandatory_keys=eapi1.mandatory_keys,
    tracked_attributes=eapi1.tracked_attributes,
    archive_suffixes=eapi1.archive_suffixes,
    optionals=_combine_dicts(eapi1.options, dict(
        doman_language_detect=True,
        transitive_use_atoms=True,
        src_uri_renames=True,
    )),
    ebd_env_options=eapi1._ebd_env_options,
)

eapi3 = EAPI.register(
    magic="3",
    parent=eapi2,
    phases=eapi2.phases,
    default_phases=eapi2.default_phases,
    metadata_keys=eapi2.metadata_keys,
    mandatory_keys=eapi2.mandatory_keys,
    tracked_attributes=eapi2.tracked_attributes,
    archive_suffixes=eapi2.archive_suffixes | frozenset(["tar.xz", "xz"]),
    optionals=_combine_dicts(eapi2.options, dict(
        prefix_capable=True,
    )),
    ebd_env_options=eapi2._ebd_env_options,
)

eapi4 = EAPI.register(
    magic="4",
    parent=eapi3,
    phases=_combine_dicts(eapi3.phases, _mk_phase_func_map("pkg_pretend")),
    default_phases=eapi3.default_phases.union([_shorten_phase_name('src_install')]),
    metadata_keys=eapi3.metadata_keys | frozenset(["REQUIRED_USE"]),
    mandatory_keys=eapi3.mandatory_keys,
    tracked_attributes=eapi3.tracked_attributes,
    archive_suffixes=eapi3.archive_suffixes,
    optionals=_combine_dicts(eapi3.options, dict(
        dodoc_allow_recursive=True,
        doins_allow_symlinks=True,
        doman_language_override=True,
        nonfatal=False,
        econf_disable_dependency_tracking=True,
        exports_replacing=True,
        has_AA=False, has_KV=False,
        has_merge_type=True,
        has_required_use=True,
        has_use_dep_defaults=True,
        trust_defined_phases_cache=True,
    )),
    ebd_env_options=eapi3._ebd_env_options,
)

eapi5 = EAPI.register(
    magic="5",
    parent=eapi4,
    phases=eapi4.phases,
    default_phases=eapi4.default_phases,
    metadata_keys=eapi4.metadata_keys,
    mandatory_keys=eapi4.mandatory_keys,
    tracked_attributes=eapi4.tracked_attributes | frozenset(["iuse_effective"]),
    archive_suffixes=eapi4.archive_suffixes,
    optionals=_combine_dicts(eapi4.options, dict(
        ebuild_phase_func=True,
        econf_disable_silent_rules=True,
        profile_iuse_injection=True,
        profile_stable_use=True,
        new_reads_stdin=True,
        required_use_one_of=True,
        sub_slotting=True,
    )),
    ebd_env_options=eapi4._ebd_env_options,
)

eapi6 = EAPI.register(
    magic="6",
    parent=eapi5,
    phases=eapi5.phases,
    default_phases=eapi5.default_phases,
    metadata_keys=eapi5.metadata_keys,
    mandatory_keys=eapi5.mandatory_keys,
    tracked_attributes=eapi5.tracked_attributes | frozenset(["user_patches"]),
    archive_suffixes=eapi5.archive_suffixes | frozenset(["txz"]),
    optionals=_combine_dicts(eapi5.options, dict(
        econf_docdir_and_htmldir=True,
        global_failglob=True,
        nonfatal_die=True,
        unpack_absolute_paths=True,
        unpack_case_insensitive=True,
        user_patches=True,
        bash_compat='4.2',
    )),
    ebd_env_options=eapi5._ebd_env_options,
)

eapi7 = EAPI.register(
    magic="7",
    parent=eapi6,
    phases=eapi6.phases,
    default_phases=eapi6.default_phases,
    metadata_keys=eapi6.metadata_keys | frozenset(["BDEPEND"]),
    mandatory_keys=eapi6.mandatory_keys,
    tracked_attributes=eapi6.tracked_attributes,
    archive_suffixes=eapi6.archive_suffixes,
    optionals=_combine_dicts(eapi6.options, dict(
        has_profile_data_dirs=True,
        has_portdir=False,
        profile_pkg_provided=False,
        has_sysroot=True,
        has_env_unset=True,
        econf_sysroot=True,
        trailing_slash='',
        is_supported=False,
    )),
    ebd_env_options=eapi6._ebd_env_options,
)
