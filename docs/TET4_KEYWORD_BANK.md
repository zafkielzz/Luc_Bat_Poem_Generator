# Tet4 Keyword Bank v1

## Cách lấy keyword

Với mỗi chủ đề, random **trong đúng family**: chọn 1 keyword ở cột **Bối cảnh**, 1 ở cột **Quan hệ/hành động**, và tùy chọn 1 ở cột **Điều mong**. Như vậy prompt luôn có một cảnh, một liên hệ giữa người với người và một hướng chúc.

Không random toàn bảng: `sân ga` ghép với `mùa màng`, hoặc `áo trắng` ghép với `cửa hàng`, thường cho hình ảnh gượng. `wish_intent` đã là ý chúc chính; keyword chỉ làm bài thơ cụ thể hơn.

Prompt copy nhanh:

```text
Viết một bài thơ Lục Bát 4 dòng chúc Tết cho {recipient}.
Ý chúc chính: {wish_intent}.
Dùng tự nhiên ít nhất hai keyword: {A} | {B} | {C-tùy chọn}.
Giọng: {tone}. Không giải thích; chỉ trả JSON theo catalogue teacher.
```

## Ngân hàng theo family

| Family | Bối cảnh (chọn 1) | Quan hệ/hành động (chọn 1) | Điều mong (chọn 0–1) |
|---|---|---|---|
| Ông bà | mâm cơm; hiên nhà; hương trầm; cành mai; sân quê; ấm trà | tay cháu; chúc thọ; kể chuyện xưa; gọi về; quây quần; nếp nhà | mạnh khỏe; an vui; sum họp; tuổi vàng; phúc lành |
| Cha mẹ, họ hàng | bếp lửa; ruộng mạ; vườn rau; chuyến xe cuối năm; mâm cỗ; ngõ quê | gói bánh; thăm nhà; phụ việc; lời con; anh em; họp mặt | bớt nhọc nhằn; thuận hòa; no ấm; yên nhà; đủ đầy |
| Vợ chồng, người yêu | căn bếp mới; sân ga; đêm giao thừa; đôi dép; lá thư; mái hiên | chung tay; đợi nhau; nắm tay; lời hẹn; sẻ chia; vun vén | bền lòng; gần nhau; trọn vẹn; ấm êm; dài lâu |
| Trẻ em, học sinh, thầy cô | bao đỏ; trang vở; sân trường; nét phấn; cổng lớp; hộp bút | chăm học; gieo chữ; dắt tay; mừng tuổi; dạy dỗ; trò ngoan | tiến bộ; vui khỏe; sáng dạ; đỗ đạt; mùa mới |
| Bạn bè, hàng xóm | chén trà; đầu ngõ; cây nêu; bàn cờ; quán nhỏ; cổng nhà | bạn xưa; bắt tay; hỏi thăm; chung ngõ; làm lành; ghé chơi | bền tình; thuận hòa; vui vầy; gặp lại; may mắn |
| Đồng nghiệp, người dẫn dắt | ca trực; đèn sáng; bàn làm việc; lịch đầu năm; ly cà phê; xưởng đêm | sát cánh; dẫn đường; bàn giao; động viên; chung sức; chỉ bảo | hanh thông; an toàn; vững nghề; thành công; gắn bó |
| Đối tác, khách hàng, kinh doanh | cửa hàng; ngày mở hàng; sổ đơn; quầy nhỏ; biển hiệu; chợ sớm | khách quen; tín nghĩa; bắt tay; giữ lời; đồng hành; cảm ơn | phát đạt; thuận buồm; bền lâu; suôn sẻ; tin cậy |
| Nông dân, công nhân, tiểu thương | ruộng mạ; chợ Tết; gánh hàng; xưởng máy; đôi găng; thúng rau | xuống đồng; đứng ca; bán hàng; gom góp; gánh vác; giữ sức | mùa bội thu; việc đều; no ấm; bình an; đủ đầy |
| Xa quê, trở về | sân ga; vé xe; gọi video; sân quê; hương trầm; căn bếp cũ | về nhà; nhớ mẹ; thắp hương; đón nhau; chờ cửa; hẹn gặp | đoàn viên; sớm về; ấm lòng; đủ mặt; yên vui |
| Cộng đồng, người phục vụ | áo trắng; đêm xuân; ngã tư; bến cảng; xe rác; trạm gác | trực Tết; giữ đường; cứu người; dọn phố; chở khách; tình nguyện | an toàn; vững tay; bình yên; khỏe mạnh; thuận ca |
| Cột mốc đời sống | nhà mới; thiệp cưới; nôi em bé; cổng trường; đơn xin việc; vali mới | xây nhà; nên duyên; đón con; tốt nghiệp; đổi việc; bắt đầu lại | khởi sắc; vững bước; nhiều hy vọng; thuận lợi; bình phục |
| Gia đình, tự thân | sổ tay; buổi sớm; chậu cây; góc bàn; cửa sổ; lịch mới | chăm mình; làm lành; giữ lời; đọc sách; bớt lo; sống chậm | bình tâm; kiên trì; khỏe mạnh; sáng rõ; an nhiên |

## Tránh các tổ hợp này

- Không lấy ba khẩu hiệu trống: `an khang | thịnh vượng | phát tài`.
- Không lặp cùng một ý ở `wish_intent` và cả ba keyword.
- Không trộn bối cảnh giữa family không liên quan.
- Bốn dòng chỉ nên có một hình ảnh trung tâm; đừng nhồi mai, đào, bánh chưng, pháo hoa và câu đối vào cùng một bài.
