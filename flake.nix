{
  description = "PowerTUI - cross-distribution hardware power control";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f system (import nixpkgs { inherit system; }));
      pyFor = pkgs: pkgs.python3.withPackages (ps: [ ps.textual ]);
    in {
      packages = forAll (system: pkgs: {
        default = pkgs.writeShellScriptBin "powertui" ''
          exec ${pyFor pkgs}/bin/python3 ${self}/app.py "$@"
        '';
      });

      apps = forAll (system: pkgs: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/powertui";
        };
      });

      devShells = forAll (system: pkgs: {
        default = pkgs.mkShell {
          packages = [ (pyFor pkgs) ];
        };
      });
    };
}
