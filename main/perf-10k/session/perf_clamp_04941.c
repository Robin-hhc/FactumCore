/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04941(unsigned int count)
{
    const unsigned int limit = 92u;
    return count > limit ? limit : count;
}
