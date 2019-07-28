

# KMP is disabled by default
%{!?KMP: %global KMP 0}

# take cpu arch from uname -m
%global _cpu_arch %(uname -m)
%global docdir /etc/mft
%global mlxfwreset_ko_path %{docdir}/mlxfwreset/


# take kernel version or default to uname -r
%{!?KVERSION: %global KVERSION 4.19.0+1}
%global kernel_version %{KVERSION}
%global krelver %(echo -n %{KVERSION} | sed -e 's/-/_/g')
# take path to kernel sources if provided, otherwise look in default location (for non KMP rpms).
%{!?K_SRC: %global K_SRC /lib/modules/%{KVERSION}/build}

%if "%{KMP}" == "1"
%global _name kernel-mft-mlnx
%else
%global _name kernel-mft
%endif

%{!?version: %global version 4.12.0}
%{!?_release: %global _release 1}
%global _kmp_rel %{_release}%{?_kmp_build_num}%{?_dist}

Name: %{_name}
Summary: %{name} Kernel Module for the %{KVERSION} kernel
Version: %{version}
Release: %{!?source:%{krelver}%{?_dist}}%{?source:%{_release}%{?_dist}}
License: Dual BSD/GPL
Group: System Environment/Kernel
BuildRoot: /var/tmp/%{name}-%{version}-build
Source: kernel-mft-%{version}.tgz
Vendor: Mellanox Technologies Ltd.
Packager: Omer Dagan <omerd@mellanox.com>
%description
mft kernel module(s)

%global debug_package %{nil}

# build KMP rpms?
%if "%{KMP}" == "1"
%global kernel_release() $(make -C %{1} kernelrelease | grep -v make | tail -1)
BuildRequires: %kernel_module_package_buildreqs
# prep file list for kmp rpm
%(cat > %{_builddir}/kmp.files << EOF
%defattr(644,root,root,755)
/lib/modules/%2-%1
%if "%{_vendor}" == "redhat"
%config(noreplace) %{_sysconfdir}/depmod.d/kernel-mft-*.conf
%endif
EOF)
%{kernel_module_package -f %{_builddir}/kmp.files -r %{_kmp_rel} }
%else
%global kernel_source() %{K_SRC}
%global kernel_release() %{KVERSION}
%global flavors_to_build default
%endif

%description
This package provides a %{name} kernel module for kernel.

%if "%{KMP}" == "1"
%package utils
Summary: KO utils for MFT
Group: System Environment/Kernel
Vendor: Mellanox Technologies Ltd.
Packager: Omer Dagan <omerd@mellanox.com>
%description utils
mft utils kernel module(s)
%endif
#
# setup module sign scripts if paths to the keys are given
#
%global WITH_MOD_SIGN %(if ( test -f "$MODULE_SIGN_PRIV_KEY" && test -f "$MODULE_SIGN_PUB_KEY" ); \
	then \
		echo -n '1'; \
	else \
		echo -n '0'; fi)

%if "%{WITH_MOD_SIGN}" == "1"
# call module sign script
%global __modsign_install_post \
    $RPM_BUILD_DIR/kernel-mft-%{version}/source/tools/sign-modules $RPM_BUILD_ROOT/lib/modules/ %{kernel_source default} || exit 1 \
%{nil}

# Disgusting hack alert! We need to ensure we sign modules *after* all
# invocations of strip occur, which is in __debug_install_post if
# find-debuginfo.sh runs, and __os_install_post if not.
#
%global __spec_install_post \
  %{?__debug_package:%{__debug_install_post}} \
  %{__arch_install_post} \
  %{__os_install_post} \
  %{__modsign_install_post} \
%{nil}

%endif # end of setup module sign scripts

%if "%{_vendor}" == "redhat"
%global __find_requires %{nil}
%endif

# set modules dir
%if "%{_vendor}" == "redhat"
%if 0%{?fedora}
%global install_mod_dir updates
%else
%global install_mod_dir extra/%{name}
%endif
%endif

%if "%{_vendor}" == "suse"
%global install_mod_dir updates
%endif

%{!?install_mod_dir: %global install_mod_dir updates}

%prep
%setup -n kernel-mft-%{version}
set -- *
mkdir source
mv "$@" source/
mkdir obj

%build
rm -rf $RPM_BUILD_ROOT
export EXTRA_CFLAGS='-DVERSION=\"%version\"'
for flavor in %{flavors_to_build}; do
	rm -rf obj/$flavor
	cp -a source obj/$flavor
	cd $PWD/obj/$flavor
	export KSRC=%{kernel_source $flavor}
	export KVERSION=%{kernel_release $KSRC}
	make KPVER=$KVERSION
	cd -
done

%install
export INSTALL_MOD_PATH=$RPM_BUILD_ROOT
export INSTALL_MOD_DIR=%{install_mod_dir}
mkdir -p %{install_mod_dir}
for flavor in %{flavors_to_build}; do
	export KSRC=%{kernel_source $flavor}
	export KVERSION=%{kernel_release $KSRC}
	install -d $INSTALL_MOD_PATH/lib/modules/$KVERSION/%{install_mod_dir}
	cp $PWD/obj/$flavor/mst_pci.ko $INSTALL_MOD_PATH/lib/modules/$KVERSION/%{install_mod_dir}/
	cp $PWD/obj/$flavor/mst_pciconf.ko $INSTALL_MOD_PATH/lib/modules/$KVERSION/%{install_mod_dir}/
    %if "%{_cpu_arch}" == "ppc64" || "%{_cpu_arch}" == "ppc64le"
        install -d $INSTALL_MOD_PATH/%{mlxfwreset_ko_path}/$KVERSION
        install $PWD/obj/$flavor/mst_ppc_pci_reset.ko $INSTALL_MOD_PATH/%{mlxfwreset_ko_path}/$KVERSION/
    %endif
done

%if "%{_vendor}" == "redhat"
# Set the module(s) to be executable, so that they will be stripped when packaged.
find %{buildroot} -type f -name \*.ko -exec %{__chmod} u+x \{\} \;

%if ! 0%{?fedora}
%{__install} -d %{buildroot}%{_sysconfdir}/depmod.d/
for module in `find %{buildroot}/ -name '*.ko*' | grep -v "%{mlxfwreset_ko_path}" | sort`
do
ko_name=${module##*/}
mod_name=${ko_name/.ko*/}
mod_path=${module/*%{name}}
mod_path=${mod_path/\/${ko_name}}
echo "override ${mod_name} * weak-updates/%{name}${mod_path}" >> %{buildroot}%{_sysconfdir}/depmod.d/%{name}-${mod_name}.conf
echo "override ${mod_name} * extra/%{name}${mod_path}" >> %{buildroot}%{_sysconfdir}/depmod.d/%{name}-${mod_name}.conf
done
%endif
%else
find %{buildroot} -type f -name \*.ko -exec %{__strip} -p --strip-debug --discard-locals -R .comment -R .note \{\} \;
%endif

%post
/sbin/depmod %{KVERSION}

%postun
/sbin/depmod %{KVERSION}

%if "%{KMP}" != "1"
%files
%defattr(-,root,root,-)
/lib/modules/%{KVERSION}/%{install_mod_dir}/
%if "%{_vendor}" == "redhat"
%if ! 0%{?fedora}
%config(noreplace) %{_sysconfdir}/depmod.d/kernel-mft-*.conf
%endif
%endif
%endif
%if "%{_cpu_arch}" == "ppc64" || "%{_cpu_arch}" == "ppc64le"
%if "%{KMP}" == "1"
%files utils
%defattr(-,root,root,-)
%endif
%{docdir}
%endif

%changelog
* Tue Jan 31 2017 Adrian Chiris <adrianc@mellanox.com>
- Added PCI reset module for PPC
* Wed Mar 19 2014 Alaa Hleihel <alaa@mellanox.com>
- Use one spec for KMP and non-KMP rpms.
* Mon Feb 18 2013 Omer Dagan <omerd@mellanox.com>
- Modified spec file to conform to KMP specifications
* Wed Aug 25 2010 Mohammad Sawalha <mohammad@mellanox.com>
- Initial revision

