#include <cstdint>
#include "parsebin.h"

#include <cstdio>
#include <stdexcept>
#include <vector>
#include <algorithm>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <cstring>

// Windows 下若要写ANSI编码，可 include <windows.h> 并调用相关转换API
#ifdef _WIN32
#include <windows.h>
#endif

// 大端转小端
static inline uint32_t swapBigEndianToHost(uint32_t v)
{
#if defined(_MSC_VER)
    return _byteswap_ulong(v);  // MSVC
#elif defined(__GNUC__) || defined(__clang__)
    return __builtin_bswap32(v); // GCC/Clang
#else
    return ((v & 0xFF000000) >> 24) |
           ((v & 0x00FF0000) >>  8) |
           ((v & 0x0000FF00) <<  8) |
           ((v & 0x000000FF) << 24);
#endif
}

static float parseHexAsFloatLittleEndian(const std::string &hex8)
{
    if (hex8.size() < 8)
        throw std::runtime_error("无效的hex字符串(长度不足8)");

    // 将hex转换为uint32_t（高位在左）
    uint32_t val = 0;
    for (char c : hex8) {
        val <<= 4;
        if      (c >= '0' && c <= '9') val |= (c - '0');
        else if (c >= 'A' && c <= 'F') val |= (c - 'A' + 10);
        else if (c >= 'a' && c <= 'f') val |= (c - 'a' + 10);
        else throw std::runtime_error("无效的hex字符");
    }

    // 大端转为本机端(小端)
    val = swapBigEndianToHost(val);

    float f;
    std::memcpy(&f, &val, sizeof(float));
    // 保留两位小数
    double temp = std::round(f * 100.0) / 100.0;
    return static_cast<float>(temp);
}

// 解析 "YYMMDDhh"、"mmssxxxx"（十进制）
static Record parseDateTimeFromTwoHex(const std::string &hex1, const std::string &hex2)
{
    if (hex1.size() < 8 || hex2.size() < 8) {
        throw std::runtime_error("时间字段长度不够");
    }

    auto decToInt = [&](const std::string &s, int pos) -> int {
        // 提取两位十进制数
        char c1 = s[pos];
        char c2 = s[pos + 1];
        if (c1 < '0' || c1 > '9' || c2 < '0' || c2 > '9') {
            throw std::runtime_error("非十进制数字");
        }
        return (c1 - '0') * 10 + (c2 - '0');
    };

    // 提取日期和时间
    int YY = decToInt(hex1, 0);  // 年
    int MM = decToInt(hex1, 2);  // 月
    int DD = decToInt(hex1, 4);  // 日
    int hh = decToInt(hex1, 6);  // 时

    int mm = decToInt(hex2, 0);  // 分
    int ss = decToInt(hex2, 2);  // 秒

    // 年份处理（假设是2000年之后的年份）
    int year = 2000 + YY;
    if (year < 2000 || year > 2100) throw std::runtime_error("年份超范围");
    if (MM < 1 || MM > 12)         throw std::runtime_error("月份无效");
    if (DD < 1 || DD > 31)         throw std::runtime_error("日期无效");
    if (hh < 0 || hh > 23)         throw std::runtime_error("小时无效");
    if (mm < 0 || mm > 59)         throw std::runtime_error("分钟无效");
    if (ss < 0 || ss > 59)         throw std::runtime_error("秒无效");

    // 将提取的日期和时间存储到 Record 结构体中
    Record r;
    r.year = year;  r.month = MM;  r.day = DD;
    r.hour = hh;    r.minute = mm; r.second = ss;

    // 生成日期字符串（如 "2025/01/10"）
    {
        std::ostringstream oss;
        oss << year << "/" << std::setw(2) << std::setfill('0') << MM << "/"
            << std::setw(2) << std::setfill('0') << DD;
        r.dateStr = oss.str();
    }

    // 生成时间字符串（如 "13:30:45"）
    {
        std::ostringstream oss;
        oss << std::setw(2) << std::setfill('0') << hh << ":"
            << std::setw(2) << std::setfill('0') << mm << ":"
            << std::setw(2) << std::setfill('0') << ss;
        r.timeStr = oss.str();
    }

    return r;
}

std::vector<Record> parseBinFile(const std::string &binFilename)
{
    std::vector<Record> rows;

    FILE* fp = std::fopen(binFilename.c_str(), "rb");
    if (!fp) {
        throw std::runtime_error("无法打开文件：" + binFilename);
    }
    // 跳过0xC0字节
    if(std::fseek(fp, 0xC0, SEEK_SET) != 0) {
        std::fclose(fp);
        throw std::runtime_error("fseek失败或文件过小：" + binFilename);
    }

    bool firstRead = true;
    while(true) {
        // 第一次132字节(33个uint32)，后续128字节(32个uint32)
        size_t blockSize = firstRead ? 132 : 128;
        std::vector<unsigned char> buffer(blockSize);

        size_t readCount = std::fread(buffer.data(), 1, blockSize, fp);
        if (readCount < blockSize) {
            // 读不足，结束
            break;
        }

        size_t intCount = firstRead ? 33 : 32;
        std::vector<uint32_t> values;
        values.reserve(intCount);

        // 每4字节组成一个uint32(大端)
        for(size_t i=0; i<intCount; ++i){
            size_t offset = i*4;
            uint32_t val=0;
            val |= (uint32_t)buffer[offset+0] <<24;
            val |= (uint32_t)buffer[offset+1] <<16;
            val |= (uint32_t)buffer[offset+2] << 8;
            val |= (uint32_t)buffer[offset+3];
            values.push_back(val);
        }

        // 如果是首块，丢弃第0个
        std::vector<uint32_t> mainVals;
        if (firstRead) {
            for(size_t i=1; i<values.size(); ++i){
                mainVals.push_back(values[i]);
            }
            firstRead=false;
        } else {
            mainVals = values;
        }

        // 转为8位hex字符串
        std::vector<std::string> hexVals;
        hexVals.reserve(mainVals.size());
        for (auto v : mainVals) {
            char buf[16];
            std::snprintf(buf, sizeof(buf), "%08X", v); // 大写HEX
            hexVals.push_back(std::string(buf));
        }

        // 每16个一组, 跳过第1个
        for(size_t i=0; i+16 <= hexVals.size(); i+=16){
            std::vector<std::string> group(hexVals.begin()+i, hexVals.begin()+i+16);

            // group[0]丢弃
            group.erase(group.begin());
            // 现在 group.size()==15
            if(group.size()<2) continue;

            // 解析时间
            Record rec;
            try {
                rec = parseDateTimeFromTwoHex(group[0], group[1]);
            } catch(...) {
                // 时间解析出错就跳过
                continue;
            }

            // 剩余13个hex解析float
            if(group.size() < 15) continue;
            std::vector<float> fvals;
            for(size_t idx=2; idx<group.size(); ++idx){
                float fv = parseHexAsFloatLittleEndian(group[idx]);
                fvals.push_back(fv);
            }

            rec.floatValues = fvals;
            rows.push_back(rec);
        }
    }

    std::fclose(fp);
    return rows;
}

void writeCsv(const std::string &csvFilename, const std::vector<Record> &rowsIn)
{
    // 复制一份并排序
    std::vector<Record> rows = rowsIn;
    std::sort(rows.begin(), rows.end(), [](const Record &a, const Record &b){
        if(a.year != b.year) return a.year < b.year;
        if(a.month!= b.month) return a.month< b.month;
        if(a.day  != b.day)   return a.day  < b.day;
        if(a.hour != b.hour)  return a.hour < b.hour;
        if(a.minute != b.minute) return a.minute<b.minute;
        return a.second < b.second;
    });

    // 去重（同一时间戳只保留第一条）
    std::vector<Record> uniqueRows;
    uniqueRows.reserve(rows.size());
    Record* last=nullptr;
    for(auto &r : rows){
        if(!last ||
            r.year!=last->year || r.month!=last->month || r.day!=last->day ||
            r.hour!=last->hour || r.minute!=last->minute || r.second!=last->second)
        {
            uniqueRows.push_back(r);
            last = &uniqueRows.back();
        }
    }

// 写CSV (Windows下示例ANSI写法，其他平台默认UTF-8)
#ifdef _WIN32
    FILE* fp = std::fopen(csvFilename.c_str(), "wb");
    if(!fp){
        throw std::runtime_error("无法创建CSV文件：" + csvFilename);
    }
    // 简易函数：字符串(UTF-8)&rarr;本地ACP(ANSI) 写入
    auto writeLine = [&](const std::string &text){
        // 将 text(UTF-8) 转为 宽字符
        int wlen = MultiByteToWideChar(CP_UTF8,0,text.c_str(),-1,NULL,0);
        if(wlen <=1) return;
        std::wstring wbuf;
        wbuf.resize(wlen);
        MultiByteToWideChar(CP_UTF8,0,text.c_str(),-1,&wbuf[0],wlen);

        // 宽字符 转 ANSI
        int alen = WideCharToMultiByte(CP_ACP,0,wbuf.c_str(),-1,NULL,0,NULL,NULL);
        if(alen <=1) return;
        std::string abuf;
        abuf.resize(alen-1);
        WideCharToMultiByte(CP_ACP,0,wbuf.c_str(),-1,&abuf[0],alen-1,NULL,NULL);

        std::fwrite(abuf.data(),1,abuf.size(),fp);
    };

    // 表头
    writeLine("日期,时间,"
              "压力设定/mbar,实际压力/mbar,"
              "设定温度/℃,实际温度/℃,"
              "设定功率/KW,实际功率/KW,"
              "加热电阻/mΩ,加热电压/V,"
              "加热电流/A,毫托计/Pa,"
              "氩气流量/SLM,温升/℃/min,"
              "氟利昂流量/SLM\n");

    // 写每条记录
    for(auto &r : uniqueRows){
        // 交换 floatValues[-2] 与 [-1]  (与 python 版保持一致)
        if(r.floatValues.size() == 13){
            std::swap(r.floatValues[11], r.floatValues[12]);
        }
        std::ostringstream oss;
        oss << r.dateStr << "," << r.timeStr << ",";
        for(size_t i=0; i<r.floatValues.size(); ++i){
            oss << r.floatValues[i];
            if(i+1<r.floatValues.size()) oss << ",";
        }
        oss << "\n";
        writeLine(oss.str());
    }

    std::fclose(fp);

#else
    // 非Windows，简单用UTF-8文本输出
    FILE* fp = std::fopen(csvFilename.c_str(), "w");
    if(!fp){
        throw std::runtime_error("无法创建CSV文件：" + csvFilename);
    }
    // 表头
    std::fprintf(fp, "%s", "日期,时间,"
                           "压力设定/mbar,实际压力/mbar,"
                           "设定温度/℃,实际温度/℃,"
                           "设定功率/KW,实际功率/KW,"
                           "加热电阻/mΩ,加热电压/V,"
                           "加热电流/A,毫托计/Pa,"
                           "氩气流量/SLM,温升/℃/min,"
                           "氟利昂流量/SLM\n");

    // 数据
    for(auto &r : uniqueRows){
        if(r.floatValues.size() == 13){
            std::swap(r.floatValues[11], r.floatValues[12]);
        }
        std::ostringstream oss;
        oss << r.dateStr << "," << r.timeStr << ",";
        for(size_t i=0; i<r.floatValues.size(); ++i){
            oss << r.floatValues[i];
            if(i+1<r.floatValues.size()) oss << ",";
        }
        oss << "\n";
        std::fprintf(fp, "%s", oss.str().c_str());
    }
    std::fclose(fp);
#endif
}
