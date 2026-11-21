/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03356(unsigned int count)
{
    const unsigned int limit = 39u;
    return count > limit ? limit : count;
}
