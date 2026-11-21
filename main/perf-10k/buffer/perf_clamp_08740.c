/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08740(unsigned int count)
{
    const unsigned int limit = 184u;
    return count > limit ? limit : count;
}
