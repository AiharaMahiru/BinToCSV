#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>

QT_BEGIN_NAMESPACE
namespace Ui {
class MainWindow;
}
QT_END_NAMESPACE

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private slots:
    // 确保这两个函数声明和 mainwindow.cpp 中的实现同名
    void onSelectBinFiles();
    void onParse();

private:
    Ui::MainWindow *ui;
};

#endif // MAINWINDOW_H
