import requests
from typing import List, Union
import json
import bz2
import os
import gzip
import gc; gc.enable()
from database import Package, db, Repository


with open("sources.json", "r") as f:
    REPOS = json.load(f)  # Some of the repositories here may not work

if not os.path.exists("repos/"):
    os.mkdir("repos/")


package_number = 0


def download_packages() -> None:
    """
    O(n*m*k) when n is the amount of repos and m is the amount of packages in each repo and k is the amount of specifiers in each package (cause of `analyze_packages`)
    """
    global REPOS
    for i in REPOS:  # Moves around the repo list
        if not os.path.exists(f"repos/{i}"):  # Checks if it's already loaded (shouldn't be but think of it as a precaution)
            try:
                response = requests.get(REPOS[i]["packages"], headers={"User-Agent": os.getenv("USER-AGENT")})  # Tried to access the Packages file with the bz2 compression
            except:
                pass
            else:
                if not response.status_code == 200:
                    response = requests.get(REPOS[i]["packages"].replace(".bz2", ""), headers={"User-Agent": os.getenv("USER-AGENT")})  # Tried to access the Packages file with no compression
                    if response.status_code == 200:
                        with open(f"repos/{i}", "wb") as f:
                            f.write(response.content)
                    else:
                        response = requests.get(REPOS[i]["packages"].replace(".bz2", ".gz"), headers={"User-Agent": os.getenv("USER-AGENT")})  # Tried to access the Packages file with the gz compression
                        if response.status_code == 200:
                            with open(f"repos/{i}", "wb") as f:
                                f.write(gzip.decompress(response.content))
                else:
                    with open(f"repos/{i}", "wb") as f:
                        f.write(bz2.decompress(response.content) if response.url.endswith("bz2") else response.content)
    analyze_packages()  # Starts alalyzing the Packages file and add the packages to the database


def analyze_packages() -> None:
    """
    O(n*m*k) when n is the number of repos and m is the number of packages in each repo and k is the amount of specifiers in each package\n
    Analyzies the packages in each repo and adds them to the database
    """
    global REPOS, package_number
    repos = os.scandir("repos")
    for repo in repos:  # Moves over the repos list
        if not repo.name.endswith(".txt"):  # Precaution
            repository = db.query(Repository).filter(Repository.name == repo.name).first()
            if repository is None:
                repository = Repository(name=repo.name)
                db.add(repository)
                db.commit()
            with open(repo.path, "rb") as f:
                text = f.read().decode("utf-8", "ignore")
                while text.endswith("\n"):
                    text = text[ : -1]
                packages = text.split("\n\n")  # Read the files and ignore letters it can't read (like chinese)


            for i in range(len(packages)):
                packages[i] = packages[i].split("\n")

            for i in range(len(packages)):
                j = 1
                while j < len(packages[i]):
                    if packages[i][j].startswith("    "):
                        packages[i][j] = packages[i][j].replace("    ", " ")
                        packages[i][j - 1] += packages[i][j]
                        del packages[i][j]
                        j -= 2
                    j += 1

            def get(package: List[str], item: str) -> Union[str, list]:
                """
                O(n) when n is the length of `package`\n
                Returns a specifier from the list
                """
                for i in package:
                    if i.startswith(item):
                        i = i.replace("\r", "")
                        while i.endswith(" "):
                            i = i[ : -1]
                        
                        if item == "Filename":
                            i = i.replace(f"{item}: ", "")
                            url = REPOS[repo.name]["download"]
                            if i.startswith("https://") or i.startswith("http://"):
                                return i
                            elif i.startswith("./"):
                                i = i[2 : ]
                            else:
                                while i.startswith("../"):
                                    url = url.split("/")
                                    url = url [ : -1]
                                    url = "/".join(url)
                            return f"{url}{i}" if url.endswith("/") else f"{url}/{i}"
                        if item == "Depends" or item == "Tag":
                            return i.replace(f'{item}: ', '').split(", ")
                        if item == "Icon" and "file://" in i:
                            return ""
                        return i.replace(f"{item}: ", "")
                return ["mobilesubstrate"] if item == "Depends" else ""


            CATEGORIES = [
                "Package",
                "Version",
                "Section",
                "Maintainer",
                "Architecture",
                "Filename",
                "Name",
                "Description",
                "Author",
                "Depends",
                "Tag",
                "Icon",
                "Depiction"
            ]

            for i in range(len(packages)):
                package = {}
                for j in CATEGORIES:
                    package[j.lower()] = get(packages[i], j)
                package["free"] = 1 if "cydia::commercial" not in package["tag"] else 0
                package["repo"] = REPOS[repo.name]["url"]
                p = db.query(Package).filter(Package.repo == package["repo"], Package.package == package["package"]).first()
                
                if p is not None:
                    p.architecture=package["architecture"],
                    p.author=package["author"],
                    p.dependencies=package["depends"],
                    p.depiction=package["depiction"],
                    p.description=package["description"],
                    p.filename=package["filename"],
                    p.free=package["free"],
                    p.icon=package["icon"],
                    p.maintainer=package["maintainer"],
                    p.name=package["name"],
                    p.package=package["package"],
                    p.repo=package["repo"],
                    p.repo_name=repo.name,
                    p.section=package["section"],
                    p.tag=package["tag"],
                    p.version=package["version"]
                else:
                    p = Package(
                        placeholder=package_number,
                        architecture=package["architecture"],
                        author=package["author"],
                        dependencies=package["depends"],
                        depiction=package["depiction"],
                        description=package["description"],
                        filename=package["filename"],
                        free=package["free"],
                        icon=package["icon"],
                        maintainer=package["maintainer"],
                        name=package["name"],
                        package=package["package"],
                        repo=package["repo"],
                        repo_name=repo.name,
                        section=package["section"],
                        tag=package["tag"],
                        version=package["version"]
                    )
                    
                    package_number += 1
                
                db.add(p)

                packages[i] = p

            q = db.query(Repository)
            for repository in q:
                if repository.name == repo.name:  # Checks if the repo is already logged in the database
                    repository.packages = packages
                    break
            else:
                repository = Repository(
                    name=repo.nam,
                    packages=packages
                )
                db.add(repository)
            
            os.remove(repo.path)  # Removes the file (no real need for this since it's on Heroku and Heroku deletes the files anyways)
    db.commit()


if __name__ == "__main__":
    download_packages()  # Download and analyze the packages
