# BinToCSV

BINT 是一个用于解析二进制文件（.bin）并将其转换为 CSV 格式的应用程序。该应用程序使用 Qt 框架构建，支持跨平台运行。

## 功能

- 选择多个 .bin 文件进行解析。
- 支持将解析结果合并为一个 CSV 文件或分别输出多个 CSV 文件。
- 解析后的数据包括日期、时间以及多个浮点数值。

## 项目结构

- `main.cpp`: 应用程序的入口点，初始化并显示主窗口。
- `mainwindow.cpp` 和 `mainwindow.h`: 主窗口的实现和定义，包含文件选择、解析和输出逻辑。
- `mainwindow.ui`: 主窗口的 UI 设计文件。
- `parsebin.cpp` 和 `parsebin.h`: 解析二进制文件的实现和定义。
- `CMakeLists.txt`: CMake 构建配置文件。
- `BINT_zh_CN.ts`: 中文翻译文件。

## 构建

1. 确保已安装 CMake 和 Qt。
2. 克隆项目到本地。
3. 在项目根目录下创建构建目录并进入：
   ```bash
   mkdir build
   cd build
   ```
4. 运行 CMake 生成构建文件：
   ```bash
   cmake ..
   ```
5. 编译项目：
   ```bash
   cmake --build .
   ```

## 运行

在构建目录下找到生成的可执行文件并运行：
```bash
./BINT
```

## 依赖

- Qt 5 或 Qt 6
- CMake 3.16 或更高版本

## 许可证

本项目采用 MIT 许可证。详细信息请参阅项目根目录下的 LICENSE 文件。

## 贡献

欢迎提交问题和拉取请求。请在提交之前确保代码通过所有测试。

## 联系方式

如有任何问题，请联系项目维护者。
