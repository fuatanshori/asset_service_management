
    function openSidebar() {

      const sidebar =
        document.getElementById('mobileSidebar');

      const overlay =
        document.getElementById('sidebarOverlay');


      sidebar.classList.remove(
        '-translate-x-full'
      );

      overlay.classList.remove(
        'opacity-0',
        'pointer-events-none'
      );

      document.body.style.overflow = 'hidden';
    }



    function closeSidebar() {

      const sidebar =
        document.getElementById('mobileSidebar');

      const overlay =
        document.getElementById('sidebarOverlay');


      sidebar.classList.add(
        '-translate-x-full'
      );

      overlay.classList.add(
        'opacity-0',
        'pointer-events-none'
      );

      document.body.style.overflow = '';
    }



    /*
     * Jika window diperbesar dari mobile
     * ke desktop, tutup sidebar.
     */

    window.addEventListener(
      'resize',
      () => {

        if (window.innerWidth >= 1024) {
          closeSidebar();
        }

      }
    );
