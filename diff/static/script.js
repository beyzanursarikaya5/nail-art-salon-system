document.addEventListener('DOMContentLoaded', () => {
    // === DOM Elementleri ===
    const accessGate = document.getElementById('access-gate');
    const bookingFormContainer = document.getElementById('booking-form-container');
    const loginButtonAuth = document.querySelector('.login-button-auth');
    const form = document.getElementById('appointment-form');

    // Form Adım Elemanları
    const steps = form ? form.querySelectorAll('.form-step') : [];
    const stepIndicators = document.querySelectorAll('.step');
    let currentStep = 1;

    // --- 1. GİRİŞ KAPISI İŞLEVSELLİĞİ ---
    
    // Simülasyon: Kullanıcı Girişi Başarılı Olduğunda
    if (loginButtonAuth) {
        loginButtonAuth.addEventListener('click', () => {
            // Gerçek bir backend'de, burada e-posta/şifre kontrolü yapılır.
            
            // Şimdilik Başarılı Giriş Simülasyonu:
            
            // 1. Giriş Kapısını Gizle
            if (accessGate) {
                accessGate.classList.add('hidden');
            }
            
            // 2. Randevu Formunu Göster
            if (bookingFormContainer) {
                bookingFormContainer.classList.remove('hidden');
            }
            
            // 3. Randevu formunun adımlarını başlat
            if (form) {
                updateSteps();
            }

            alert('Giriş başarılı! Randevuya devam edebilirsiniz.');
        });
    }


    // --- 2. ÇOK ADIMLI FORM İŞLEVSELLİĞİ ---
    
    // Fonksiyon: Adımları Güncelleme
    function updateSteps() {
        if (!steps.length) return;

        steps.forEach((step, index) => {
            step.classList.remove('active');
            stepIndicators[index].classList.remove('active');
            
            if (parseInt(step.dataset.step) === currentStep) {
                step.classList.add('active');
            }
            if (parseInt(stepIndicators[index].innerText.charAt(0)) <= currentStep) {
                stepIndicators[index].classList.add('active');
            }
        });
        updateSummary();
    }

    // Fonksiyon: Özeti Güncelleme (Önceki cevaptaki gibi)
    function updateSummary() {
        // ... (Bu kısım, Adım 3'teki özet metinlerini doldurur)
        if (currentStep === 3) {
            document.getElementById('summary-date').innerText = document.getElementById('booking-date').value || 'Seçilmedi';
            document.getElementById('summary-time').innerText = document.getElementById('booking-time').value || 'Seçilmedi';
            document.getElementById('summary-design').innerText = document.getElementById('design-name').innerText;
            // Diğer özet güncellemeleri...
        }
    }

    // Olay Dinleyicileri (Form İçi Geçişler)
    if (form) {
        form.addEventListener('click', (e) => {
            // NEXT Butonu
            if (e.target.classList.contains('next-step-button')) {
                // Basit doğrulama yap
                const currentInputs = steps[currentStep - 1].querySelectorAll('input[required], select[required]');
                let isValid = true;
                currentInputs.forEach(input => {
                    if (!input.value) {
                        isValid = false;
                        input.style.borderColor = 'red';
                    } else {
                        input.style.borderColor = '#ddd';
                    }
                });

                if (isValid && currentStep < steps.length) {
                    currentStep++;
                    updateSteps();
                } else if (!isValid) {
                    // Alert sadece zorunlu alanlar boşsa çıksın
                    // alert("Lütfen gerekli alanları doldurun.");
                }
            }
            
            // PREV Butonu
            if (e.target.classList.contains('prev-step-button')) {
                if (currentStep > 1) {
                    currentStep--;
                    updateSteps();
                }
            }
        });

        // Randevu Tamamlandı (Backend'e Gönderme)
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            alert('Tebrikler! Randevunuz başarıyla oluşturuldu ve onay için e-posta adresinize gönderildi.');
            // Gerçek projede: AJAX/Fetch ile veriler backend'e gönderilir.
        });
    }

    // Başlangıç Durumunu Ayarlama: Formu gizle, kapıyı göster
    if (accessGate && bookingFormContainer) {
        bookingFormContainer.classList.add('hidden'); // Sayfa yüklenince formu gizle
        accessGate.classList.remove('hidden'); // Kapıyı göster
    }
});



// randevu.html dosyasındaki <script> bloğuna ekleyin:

// --- KRİTİK: TASARIM BİLGİSİNİ AL VE FORMU DOLDUR ---

function loadSelectedDesign() {
    const savedDesignId = localStorage.getItem('selected_design_id');
    const savedDesignPrice = localStorage.getItem('selected_design_price');
    
    // Eğer tarayıcı belleğinde bir tasarım bilgisi varsa
    if (savedDesignId) {
        // 1. Nail Art'ı otomatik olarak seçili hale getir (service_id=7 olduğunu varsayıyoruz)
        serviceCheckboxes.forEach(checkbox => {
            if (checkbox.getAttribute('data-name').trim() === 'Nail Art') {
                checkbox.checked = true;
            }
        });

        // 2. Formu güncelle ki fiyat hesaplansın ve alt seçenekler açılsın
        updateForm(); 

        // 3. Tasarım Seçenekleri menüsünden Galeriyi seçili hale getir
        designSelection.value = 'gallery';
        setupNailArtOptions(); // Görünümü ayarla

        // 4. Fiyatlandırma: Ek ücreti direkt uygulayalım
        currentSurcharge = parseFloat(savedDesignPrice || 0.0);
        designIdInput.value = savedDesignId;
        
        updatePrice();

        // 5. Temizleme: Veriyi kullandıktan sonra bellekten sil
        localStorage.removeItem('selected_design_id');
        localStorage.removeItem('selected_design_price');
    }
}

// document.addEventListener('DOMContentLoaded', updateForm); çağrısından hemen sonra çağırın:
document.addEventListener('DOMContentLoaded', loadSelectedDesign);