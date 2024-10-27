# Maintainer: Jajasek <jachym.mierva@gmail.com>
pkgname=timeline
pkgver=r31.6c8d048.dev
pkgrel=1
epoch=
pkgdesc="Scripts for parsing and filtering structured notes, integrated with neovim and kitty. Development version."
arch=(any)
url="https://github.com/Jajasek/timeline"
license=('GPL-3.0-or-later')
groups=()
depends=('python-thefuzz' 'kitty' 'neovim')
makedepends=()
checkdepends=()
optdepends=()
provides=()
conflicts=('timeline')
replaces=()
backup=()
options=()
install=
changelog=
source=()  # makepkg doesn't support local directory as source
noextract=()
sha256sums=()
validpgpkeys=()

# This PKGBUILD is used to build the current state of the project directory,
# regardless of the state of git. We do not copy any sources to srcdir, just
# cd to the project directory and run 'make install' from there.

projectdir=$PWD

# prepare() {
#   # we are in $srcdir. Relying on the default ~/projects/timeline/src.
#   # manually copying the sources here
#   mkdir -p $pkgname
#   cp -r ../source/* $pkgname
# }

pkgver() {
  # cd "$srcdir/$pkgname"
  cd "$projectdir"
  # diferentiate the development version built from non-commited source by adding dev
  printf "r%s.%s.dev" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

package() {
  cd "$projectdir"
  echo "$projectdir"
  # INSTALL_DIR should be renamed to prefix
  make DESTDIR="$pkgdir/" INSTALL_DIR="/usr" install
}
