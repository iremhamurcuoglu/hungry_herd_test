# Hungry Herd - Web Deployment Guide

Bu oyun artık web üzerinde oynanabilir hale getirildi ve GitHub Pages ile otomatik olarak yayınlanacak şekilde ayarlandı.

## Nasıl Yayınlanır?

1.  **Kodları GitHub'a Yükleyin:**
    Değişiklikleri mevcut GitHub deponuza gönderin (push):
    ```bash
    git add .
    git commit -m "Web compatibility and deployment workflow added"
    git push origin main
    ```

2.  **GitHub Actions'ı İzleyin:**
    GitHub deponuzda "Actions" sekmesine gidin. `Pygame Web Build` iş akışının çalıştığını göreceksiniz. Bu işlem bittiğinde `gh-pages` adında yeni bir dal (branch) oluşacaktır.

3.  **GitHub Pages Ayarlarını Yapın:**
    - GitHub deponuzda `Settings` -> `Pages` yolunu izleyin.
    - "Build and deployment" kısmında `Branch` olarak `gh-pages` seçin ve `/ (root)` olarak kaydedin.

4.  **Oyunun Keyfini Çıkarın:**
    Birkaç dakika sonra oyununuz `https://[kullanıcı-adınız].github.io/[repo-adınız]/` adresinde yayında olacaktır!

## Teknik Detaylar

-   **pygbag:** Python kodunuzu WebAssembly (WASM) formatına dönüştürerek tarayıcıda çalışmasını sağlar.
-   **asyncio:** Web üzerinde oyunun takılmadan çalışması için asenkron bir döngü kullanıldı.
