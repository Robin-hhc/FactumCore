/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05632(unsigned int count)
{
    const unsigned int limit = 136u;
    return count > limit ? limit : count;
}
