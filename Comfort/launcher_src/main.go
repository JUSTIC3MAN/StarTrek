// Comfort.exe - starts the Comfort app server (no console) and opens it in an Edge app window.
package main

import (
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

type launcherCfg struct {
	Python string `json:"python"`
	Port   int    `json:"port"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
}

func msg(text string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	box := user32.NewProc("MessageBoxW")
	t, _ := syscall.UTF16PtrFromString(text)
	c, _ := syscall.UTF16PtrFromString("Comfort")
	box.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(c)), 0x10)
}

func open(port int) bool {
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("127.0.0.1:%d", port), 400*time.Millisecond)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

func exists(p string) bool { _, err := os.Stat(p); return err == nil }

// newest modification time of Comfort's code files on disk (unix seconds)
func diskVersion(dir string) float64 {
	v := 0.0
	for _, f := range []string{"comfort.py", "comfort_app.py", "comfort_agent.py", "comfort_flows.py"} {
		if st, err := os.Stat(filepath.Join(dir, f)); err == nil {
			t := float64(st.ModTime().UnixNano()) / 1e9
			if t > v {
				v = t
			}
		}
	}
	return v
}

// version reported by the running app (0 = old app without a version)
func runningVersion(url string) float64 {
	c := http.Client{Timeout: 4 * time.Second}
	r, err := c.Get(url + "api/state")
	if err != nil {
		return -1
	}
	defer r.Body.Close()
	var st struct {
		Version float64 `json:"version"`
	}
	json.NewDecoder(r.Body).Decode(&st)
	return st.Version
}

func main() {
	exe, _ := os.Executable()
	dir := filepath.Dir(exe)
	cfg := launcherCfg{Python: `A:\ClaudeComfy\venv\Scripts\pythonw.exe`, Port: 8790, Width: 1440, Height: 920}
	if b, err := os.ReadFile(filepath.Join(dir, "launcher.json")); err == nil {
		json.Unmarshal(b, &cfg)
	}
	url := fmt.Sprintf("http://127.0.0.1:%d/", cfg.Port)

	if open(cfg.Port) && runningVersion(url) < diskVersion(dir)-1 {
		// an older Comfort is running: stop it so the updated one starts
		c := http.Client{Timeout: 4 * time.Second}
		c.Post(url+"api/quit", "application/json", strings.NewReader("{}"))
		for i := 0; i < 60 && open(cfg.Port); i++ {
			time.Sleep(250 * time.Millisecond)
		}
	}

	if !open(cfg.Port) {
		if !exists(cfg.Python) {
			msg("Python not found:\n" + cfg.Python + "\n\nEdit launcher.json next to Comfort.exe.")
			return
		}
		cmd := exec.Command(cfg.Python, "-s", filepath.Join(dir, "comfort_app.py"))
		cmd.Dir = dir
		cmd.Env = append(os.Environ(), "PYTHONUTF8=1", "PYTHONNOUSERSITE=1", "PYTHONPATH=")
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000 | 0x00000200} // NO_WINDOW | NEW_PROCESS_GROUP
		if err := cmd.Start(); err != nil {
			msg("Could not start Comfort:\n" + err.Error())
			return
		}
		ok := false
		for i := 0; i < 120 && !ok; i++ {
			time.Sleep(250 * time.Millisecond)
			ok = open(cfg.Port)
		}
		if !ok {
			msg("Comfort did not start. See app.log and comfort.log in:\n" + dir)
			return
		}
	}

	for _, edge := range []string{
		`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`,
		`C:\Program Files\Microsoft\Edge\Application\msedge.exe`,
		`C:\Program Files\Google\Chrome\Application\chrome.exe`,
	} {
		if exists(edge) {
			c := exec.Command(edge, "--app="+url, fmt.Sprintf("--window-size=%d,%d", cfg.Width, cfg.Height))
			if c.Start() == nil {
				return
			}
		}
	}
	exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
}
