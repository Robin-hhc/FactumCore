/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05490(unsigned int count)
{
    const unsigned int limit = 212u;
    return count > limit ? limit : count;
}
