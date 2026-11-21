/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08881(unsigned int count)
{
    const unsigned int limit = 91u;
    return count > limit ? limit : count;
}
