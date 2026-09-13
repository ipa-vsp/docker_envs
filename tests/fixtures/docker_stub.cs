// Native executable fixture: verify the argv Docker receives on PS 5.1 and 7.
using System;
using System.IO;
using System.Linq;
using System.Text;

class DockerStub
{
    static int Main(string[] args)
    {
        string log = Environment.GetEnvironmentVariable("DOCKER_TEST_LOG");
        File.AppendAllText(log, String.Join("\t", args.Select(a => Convert.ToBase64String(Encoding.UTF8.GetBytes(a)))) + "\n");
        string mode = Environment.GetEnvironmentVariable("DOCKER_TEST_MODE") ?? "";
        if (args[0] == "info")
        {
            if (mode == "offline")
            {
                Console.Error.WriteLine("failed to connect: dockerDesktopLinuxEngine pipe is missing");
                return 1;
            }
            Console.WriteLine(mode == "windows" ? "windows" : "linux");
        }
        else if (args.Length > 1 && args[0] == "buildx")
        {
            if (args[1] == "version")
            {
                if (mode == "no-buildx") return 1;
                Console.WriteLine("github.com/docker/buildx test");
            }
            if (args[1] == "inspect")
            {
                Console.WriteLine("Name:   desktop-linux");
                Console.WriteLine("Driver: " + (mode == "remote" ? "docker-container" : "docker"));
            }
            if (args[1] == "build" && mode == "fail-second")
            {
                int count = File.ReadLines(log).Count(line => line.StartsWith("YnVpbGR4\tYnVpbGQ=\t"));
                if (count == 2) { Console.Error.WriteLine("fixture build failure"); return 23; }
            }
        }
        return 0;
    }
}
