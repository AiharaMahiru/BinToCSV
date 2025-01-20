#include "mainwindow.h"
#include "ui_mainwindow.h"
#include <QFileDialog>
#include <QMessageBox>
#include "parsebin.h"

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
{
    ui->setupUi(this);

    // 连接信号与槽
    connect(ui->btnSelect, &QPushButton::clicked, this, &MainWindow::onSelectBinFiles);
    connect(ui->btnParse,  &QPushButton::clicked, this, &MainWindow::onParse);

    // 默认选中“分别输出CSV”
    ui->radioSeparate->setChecked(true);
}

MainWindow::~MainWindow()
{
    delete ui;
}

void MainWindow::onSelectBinFiles()
{
    QStringList paths = QFileDialog::getOpenFileNames(
        this,
        tr("选择 .bin 文件"),
        QString(),
        tr("BIN Files (*.bin);;All Files (*.*)"));
    if (paths.isEmpty()) {
        return;
    }
    // 显示到 listWidget
    ui->listWidget->clear();
    for (const QString &p : paths) {
        ui->listWidget->addItem(p);
    }
}

void MainWindow::onParse()
{
    int count = ui->listWidget->count();
    if (count == 0) {
        QMessageBox::warning(this, tr("提示"), tr("尚未选择任何 .bin 文件！"));
        return;
    }

    // 判断是“合并输出”还是“分别输出”
    bool mergeToOne = ui->radioMerge->isChecked();

    // 收集列表中文件路径
    QStringList binPaths;
    for (int i = 0; i < count; ++i) {
        binPaths << ui->listWidget->item(i)->text();
    }

    if (mergeToOne) {
        // 让用户选择合并后CSV的保存路径
        QString outFilename = QFileDialog::getSaveFileName(
            this,
            tr("保存合并后的 CSV"),
            QString(),
            tr("CSV Files (*.csv);;All Files (*.*)"));
        if (outFilename.isEmpty()) {
            return; // 用户取消
        }

        std::vector<Record> mergedRecords;
        // 解析所有 bin
        for (const QString &binPath : binPaths) {
            try {
                std::vector<Record> recs = parseBinFile(binPath.toStdString());
                mergedRecords.insert(mergedRecords.end(), recs.begin(), recs.end());
            } catch (const std::exception &e) {
                QMessageBox::critical(this, tr("错误"),
                                      tr("解析失败：%1\n%2").arg(binPath, e.what()));
                return;
            }
        }
        // 写入CSV
        try {
            writeCsv(outFilename.toStdString(), mergedRecords);
        } catch (const std::exception &e) {
            QMessageBox::critical(this, tr("错误"),
                                  tr("写CSV失败：\n%1").arg(e.what()));
            return;
        }

        QMessageBox::information(this, tr("完成"),
                                 tr("合并输出成功，已生成：\n%1").arg(outFilename));
    }
    else {
        // 分别输出
        QStringList successList;
        for (const QString &binPath : binPaths) {
            try {
                std::vector<Record> recs = parseBinFile(binPath.toStdString());
                // 生成同名 .csv (仅替换后缀)
                QString csvPath = binPath;
                int dotPos = csvPath.lastIndexOf('.');
                if (dotPos > 0) {
                    csvPath = csvPath.left(dotPos) + ".csv";
                } else {
                    csvPath += ".csv";
                }
                writeCsv(csvPath.toStdString(), recs);
                successList << csvPath;
            } catch (const std::exception &e) {
                QMessageBox::critical(this, tr("错误"),
                                      tr("解析失败：%1\n%2").arg(binPath, e.what()));
            }
        }
        if (!successList.isEmpty()) {
            QMessageBox::information(this, tr("完成"),
                                     tr("处理完成！生成的CSV文件：\n%1").arg(successList.join("\n")));
        }
    }
}
