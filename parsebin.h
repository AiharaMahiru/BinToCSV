#ifndef PARSEBIN_H
#define PARSEBIN_H

#include <string>
#include <vector>

/// 一条解析结果记录
struct Record {
    int year;
    int month;
    int day;
    int hour;
    int minute;
    int second;
    std::string dateStr; // "YYYY/MM/DD"
    std::string timeStr; // "hh:mm:ss"
    std::vector<float> floatValues;
};

/**
 * @brief parseBinFile
 *  解析给定bin文件，返回记录列表。
 *  若文件异常或解析错误，可能抛出 std::runtime_error。
 */
std::vector<Record> parseBinFile(const std::string &binFilename);

/**
 * @brief writeCsv
 *  将记录列表按(年,月,日,时,分,秒)排序并去重，然后写入到csv文件
 *  若写入失败或其他异常，可能抛出 std::runtime_error。
 */
void writeCsv(const std::string &csvFilename, const std::vector<Record> &rows);

#endif // PARSEBIN_H
