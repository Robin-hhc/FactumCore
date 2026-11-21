/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07632(unsigned int count)
{
    const unsigned int limit = 23u;
    return count > limit ? limit : count;
}
