# 🧧 TÀI LIỆU THIẾT KẾ & Ý TƯỞNG FRONTEND "ÔNG ĐỒ AI" (FOR GOOGLE STITCH & ANIMATION)

> **Tên sản phẩm:** Ông Đồ AI – Sinh Thơ Lục Bát & Thiệp Mừng Năm Mới 3D Interactive  
> **Triết lý sản phẩm:** *"Năm nay đào lại nở – LẠI THẤY ông đồ xưa"*. AI không thay thế Ông Đồ cổ truyền, AI giúp Ông Đồ ngồi lại với mùa xuân dân tộc.

---

## 🎨 1. HỆ THỐNG THẨM MỸ & THIẾT KẾ (DESIGN SYSTEM TOKENS)

### 🔴 Bảng Màu Tết Cổ Truyền (Palettes)
- **Đỏ Dó Thắm (Primary Red):** `#901111` / `#c92a2a` / `#e03131` (Màu đỏ giấy dó, câu đối đỏ, lồng đèn Tết).
- **Vàng Hoàng Kim (Luxury Gold):** `#ffd700` / `#fcc419` / `#ffe066` (Màu chữ thư pháp dát vàng, quầng sáng lồng đèn, nhụy hoa).
- **Mực Tàu Huyền Nhất (Ink Black):** `#120507` / `#1a070a` / `#2b0d0e` (Màu nghiên mực đá, mài mực thư pháp, nền thẫm).
- **Giấy Dó Kem (Paper Parchment):** `#f7eed7` / `#fce8d5` (Màu mặt sau thiệp giấy dó cổ truyền).
- **Hồng Đào Miền Bắc (Peach Pink):** `#ff1a53` / `#ff4d79` / `#ff85a2` / `#e60039` (Cánh hoa đào thắm, bích, phai).
- **Vàng Mai Miền Nam (Apricot Gold):** `#ffd700` / `#fcc419` / `#ffec99` / `#d9480f` (Cánh hoa mai vàng, nhụy cam đỏ).

### ✍️ Phông Chữ Thư Pháp & Tiêu Đề (Typography)
- **Thư pháp chính (Calligraphy):** `Charm` / `Dancing Script` (Dành cho 4 câu thơ Lục Bát, chữ ban ban thư pháp Hán-Nôm).
- **Tiêu đề cổ điển (Serif Title):** `Playfair Display` (Dành cho các tiêu đề lớn, banner hoàng kim).
- **Văn bản hệ thống (Sans Body):** `Be Vietnam Pro` (Dành cho form nhập, hướng dẫn, thẻ điển tích).

---

## 🌸 2. HIỆU ỨNG NỀN & BẦU KHÔNG KHÍ TẾT (TET AMBIENT BACKGROUND)

1. **Ảnh Nền Nghệ Thuật Tết (`tet_bg.jpg`):**
   - Ảnh nền đỏ nhung thẫm 16:9, lồng đèn đỏ tỏa sáng, quầng sáng hoàng kim, họa tiết mây cuộn Đông Á và trống đồng Đông Sơn.
   - Kết hợp lớp phủ tối mờ (`vignette gradient`) giúp tạo độ tương phản tốt nhất cho giao diện.
2. **Lồng Đèn Đỏ Xuân Treo Đung Đưa:**
   - 2 lồng đèn treo ở 2 góc trên màn hình, khắc chữ Hán `福` (Phúc) và `春` (Xuân).
   - Đung đưa tự nhiên theo chu kỳ sine wave (`rotate: [-2.5deg, 2.5deg]`).
3. **Hiệu Ứng Hoa Rơi Nam - Bắc (`BlossomPetals`):**
   - Xoay quanh 2 loài hoa Tết: **Hoa Đào miền Bắc** (5 cánh hồng nhụy vàng) & **Hoa Mai miền Nam** (5 cánh vàng nhụy cam đỏ).
   - Tỷ lệ hòa trộn: ~55% Hoa Đào + 45% Hoa Mai Vàng.
   - Vật lý gió chao nghiêng tự nhiên + **Hover/Click Interaction**: Rê chuột hoa dạt ra, nhấp click tung pháo hoa cánh đào/mai.
4. **Bụi Kim Tuyến Vàng (`Golden Sparkle Dust`):**
   - Các hạt kim tuyến vàng phát sáng lơ lửng nhấp nháy khắp màn hình.

---

## 📜 3. LUỒNG TRẢI NGHIỆM 4 BƯỚC XIN THƠ & LẬT THIỆP 3D

### 🔹 BƯỚC 1: Form Xin Chữ Đầu Xuân (`XinChuForm`)
- **Ý nguyện mừng xuân:** Người dùng chọn đối tượng chúc Tết (Ông Bà, Cha Mẹ, Thầy Cô, Bạn Bè, Công Danh, Tình Duyên...).
- **Cụm Nụ Hoa Hái Lộc:** Nút chọn nhanh từ khóa mừng xuân (An khang, Thịnh vượng, Sức khỏe, Đỗ đạt, Sum vầy...).
- **Nhập lời nhắn kín:** Nhập lời chúc riêng tư xuất hiện ẩn ở mặt sau thiệp.

### 🔹 BƯỚC 2: Animation Mài Mực Loader (`InkGrindingLoader`)
- **Visual:** Thỏi mực tàu mài xoay tròn trên nghiên mực đá đen nhung (`animate-ink-grind`).
- **Nội dung giảm latency:** Carousel tự động chuyển slide các điển tích & phong tục Tết (Tục xông đất, Cây nêu, Bánh chưng, Tranh Đông Hồ, Tục xin chữ).

### 🔹 BƯỚC 3: Animation Thư Pháp Mực Loang & Âm Thanh Cọ (`PoemInkReveal`)
- **Từng nét chữ hiện ra:** Từng ký tự thơ Lục Bát xuất hiện với hiệu ứng loang mực nhòe (`inkBleed`) trên mặt giấy dó.
- **Âm thanh cọ sột soạt:** Giả lập tiếng cọ quét trên giấy dó cổ truyền bằng Synth Web Audio API (`playBrushStrokeSound`).

### 🔹 BƯỚC 4: Thiệp 3D Lật Mặt & Khắc Con Dấu Triện (`GreetingCard`)
- **3D Card Flip:** Thiệp lật 180 độ qua lại giữa mặt trước (Thơ Lục Bát + Chữ ban thư pháp Hán-Nôm) và mặt sau (Lời nhắn kín riêng tư).
- **Đóng Dấu Triện Red Seal (`stampDown`):** Con dấu triện đỏ đóng xuống với âm thanh nổ pháo hoa mừng xuân (`canvas-confetti`).
- **Khóa 1 câu thơ trọn 1 dòng (`whiteSpace: nowrap`):** Đảm bảo câu Lục 6 tiếng và câu Bát 8 tiếng luôn vừa vặn không vỡ dòng.

---

## 🎨 4. CANVAS EDITOR & KHO LƯU TRỮ THIỆP

1. **Canvas Editor Trực Quan (`CardEditor`):**
   - Sửa nội dung 4 câu thơ trực tiếp.
   - Chọn Phông chữ (Charm, Dancing Script, Playfair Display, Be Vietnam Pro) & Cỡ chữ (Sm, Md, Lg, Xl).
   - Chọn Màu chữ, Màu nền thiệp, Tên dấu triện cá nhân hóa.
   - Bộ 5 Template mẫu: Giấy Dó Thắm, Giấy Dó Hoàng Kim, Mực Tàu Huyền Nhất, Hoàng Kim Cát Tường, Lụa Đào Hồng Thắm.
2. **Kho Lưu Trữ Thiệp (`CardGallery` & `storage.ts`):**
   - Lưu tự động vào `localStorage`.
   - Giao diện lưới xem lại, sửa lại trong Canvas Editor, sao chép link chia sẻ, tải ảnh PNG hoặc xóa.

---

## 🚀 5. TRẢI NGHIỆM CHIA SẺ & TRANG HỘI XUÂN TẾT WOW (`SharedCardView`)

### 🔗 Mã Hóa Link Share (`share.ts`)
- Mã hóa toàn bộ dữ liệu thiệp thành chuỗi Base64 an toàn trong URL parameter `?share=...`.
- Người nhận mở link là xem thiệp trực tiếp không cần đăng nhập.

### 🎆 Page 1: Màn Chào Mừng & Lật Thiệp 3D
- **Pháo hoa chào đón:** Vừa mở link tự động bắn pháo hoa mừng xuân + hoa đào hoa mai rơi lơ lửng.
- **Bàn tay hướng dẫn nhún nhảy:** Chỉ báo `👇 Tap / Chạm vào thiệp để lật mặt sau đọc lời nhắn kín`.
- **Wipe / Slide Trượt Ngang Sang Page 2:** Nút bấm rực rỡ và cử chỉ **Swipe Left (Vuốt màn hình sang trái)** trượt ngang màn hình sang Page 2.

### 🧧 Page 2: Vòng Lì Xì Bí Mật 3D (Blind Box Carousel) & Hội Xuân
1. **Quỹ đạo Lì Xì Xoay Tròn 3D:**
   - 6 Phong Bao Lì Xì Bí Mật (Trạng thái ẩn ban đầu: `福` Phúc, `祿` Lộc, `壽` Thọ, `喜` Hỷ, `財` Tài, `吉` Cát) liên tục chuyển động xoay tròn 3D lơ lửng.
2. **Cơ chế Hover-to-Pause (Không gộp xấp layout):**
   - Khi rê chuột vào bao lì xì bất kỳ, vòng xoay **dừng lại ngay lập tức tại đúng vị trí vòng tròn**.
   - Phong bao được di chuột **phóng to 1.25 lần tại chỗ (`scale 1.25`)**, giữ nguyên vị trí phân bổ hình tròn.
3. **Modal Bóc Lì Xì Bất Ngờ:**
   - Khi nhấp chọn, Modal pop-up bật lên với nổ pháo hoa mừng xuân, lật mở tên Lì Xì, câu chúc may mắn và thẻ điển tích văn hóa Tết.
4. **Vòng lặp lan tỏa (Viral CTA):**
   - Nút bấm `🧧 TỰ XIN THƠ & TẠO THIỆP MỚI CHO NGƯỜI THÂN` để tiếp tục luồng tạo thiệp.

---

## 🎮 6. TÍNH NĂNG TƯƠNG TÁC BỔ SUNG

- **Nối Vần Lục Bát (`LucBatGame`):** Mini-game tương tác chấm vần Lục Bát (luật Bằng/Trắc tiếng 2-4-6-8, vần lưng, vần chân).
- **Hái Lộc Đầu Xuân (`HaiLocGame`):** Chọn nụ hoa mai/đào nhận ý nguyện đầu năm.
- **Góc Nhìn Văn Hóa (`ConceptSection`):** Bảng đối chiếu ẩn dụ văn hóa giữa Ông Đồ xưa và AI ngày nay.

---
*Tài liệu này được tổng hợp đầy đủ mã thiết kế, hiệu ứng animation và luồng tương tác để đưa vào Google Stitch / AI Animation Generator.*
